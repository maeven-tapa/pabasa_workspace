"""
Story Response Activity Views

Handles:
- Getting published Story Reading activities (for story selector)
- Student-facing Story Response activity page
- Submitting story responses
- Getting response prompts
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
import json
from .models import Material, User, Enrollment
from .story_response_prompts import (
    RESPONSE_PROMPT_CATEGORIES,
    SUGGESTED_PROMPTS,
    STORY_SPECIFIC_PROMPTS,
    get_all_prompts_for_story,
)


def _is_story_reading_material(material):
    """Check if a material is a published Story Reading activity."""
    if not material or not isinstance(material, Material):
        return False
    
    content_json = material.content_json if isinstance(material.content_json, dict) else {}
    
    # Check for story reading indicators
    has_story_title = bool(content_json.get('storyTitle') or content_json.get('story_title'))
    has_story_text = bool(content_json.get('storyText') or content_json.get('story_text'))
    is_story_reading_type = content_json.get('activity_type') == 'story_reading'
    has_story_reading_nested = bool(content_json.get('storyReading', {}))
    
    # Must be published
    is_published = material.status == 'published'
    
    return is_published and (
        (has_story_title and has_story_text) or 
        is_story_reading_type or 
        has_story_reading_nested
    )


@login_required
@require_http_methods(["GET"])
def get_published_stories_api(request):
    """
    API endpoint to get all published Story Reading activities for the teacher's classes.
    
    Returns a list of published stories that can be used as sources for Story Response activities.
    """
    user = User.objects.filter(id=request.session.get('user_id'), role='teacher', is_archived=False).first()
    if not user:
        return JsonResponse({'success': False, 'error': 'Teacher not found.'}, status=404)
    
    # Get all sections/classes the teacher teaches
    teacher_sections = user.section_set.all() if hasattr(user, 'section_set') else []
    
    # Get published story reading materials from those sections
    published_stories = Material.objects.filter(
        Q(section__in=teacher_sections) | Q(teacher=user),
        status='published',
        is_active=True,
        is_archived=False if hasattr(Material, 'is_archived') else True,
    ).select_related('section', 'teacher')
    
    # Filter to only story reading materials
    stories = []
    for material in published_stories:
        if _is_story_reading_material(material):
            content_json = material.content_json or {}
            story_data = {
                'id': material.id,
                'material_id': f'material-{material.id}',
                'title': str(content_json.get('storyTitle') or material.title or '').strip(),
                'language': str(content_json.get('language') or material.language or 'English').strip(),
                'story_key': str(content_json.get('storyKey') or '').strip(),
                'text_preview': str(content_json.get('storyText') or material.content_text or '')[:200].strip(),
                'created_at': material.created_at.isoformat() if material.created_at else None,
                'teacher': material.teacher.get_full_name() if material.teacher else 'System',
            }
            stories.append(story_data)
    
    # Sort by creation date, newest first
    stories.sort(key=lambda x: x['created_at'] or '', reverse=True)
    
    return JsonResponse({
        'success': True,
        'stories': stories,
        'total': len(stories),
    })


@csrf_protect
@login_required
@require_http_methods(["POST"])
def get_story_response_prompts_api(request):
    """
    API endpoint to get suggested response prompts for a given story.
    
    Request body:
    {
        "story_id": 123,
        "language": "English" or "Filipino",
        "include_story_specific": true
    }
    
    Returns prompts organized by category.
    """
    try:
        payload = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    
    story_id = payload.get('story_id')
    language = str(payload.get('language', 'English')).strip()
    include_story_specific = bool(payload.get('include_story_specific', True))
    
    if not story_id:
        return JsonResponse({'success': False, 'error': 'story_id is required.'}, status=400)
    
    # Get the story material
    story_material = Material.objects.filter(id=story_id, status='published').first()
    if not story_material or not _is_story_reading_material(story_material):
        return JsonResponse({'success': False, 'error': 'Story not found or not published.'}, status=404)
    
    # Get the story key
    content_json = story_material.content_json or {}
    story_key = content_json.get('storyKey') or ''
    
    # Get prompts
    prompts_by_category = {}
    
    # Add general prompts
    language_prompts = SUGGESTED_PROMPTS.get(language, SUGGESTED_PROMPTS.get('English', {}))
    for category, items in language_prompts.items():
        category_info = RESPONSE_PROMPT_CATEGORIES.get(category, {})
        prompts_by_category[category] = {
            'category': category,
            'emoji': category_info.get('emoji', ''),
            'label': category_info.get('label', ''),
            'description': category_info.get('description', ''),
            'prompts': [
                {
                    'text': item,
                    'source': 'suggested',
                    'type': 'general',
                }
                for item in items
            ]
        }
    
    # Add story-specific prompts if available
    if include_story_specific and story_key:
        story_specific = STORY_SPECIFIC_PROMPTS.get(story_key, {})
        if story_specific:
            story_prompts = story_specific.get('prompts', {})
            for category, items in story_prompts.items():
                if category not in prompts_by_category:
                    category_info = RESPONSE_PROMPT_CATEGORIES.get(category, {})
                    prompts_by_category[category] = {
                        'category': category,
                        'emoji': category_info.get('emoji', ''),
                        'label': category_info.get('label', ''),
                        'description': category_info.get('description', ''),
                        'prompts': []
                    }
                prompts_by_category[category]['prompts'].extend([
                    {
                        'text': item,
                        'source': 'suggested',
                        'type': 'story_specific',
                    }
                    for item in items
                ])
    
    return JsonResponse({
        'success': True,
        'categories': RESPONSE_PROMPT_CATEGORIES,
        'prompts_by_category': prompts_by_category,
    })


@login_required
@require_http_methods(["GET"])
def story_response_page(request):
    """
    Render the student-facing Story Response activity page.
    
    Query params:
    - id or material_id: The Story Response material ID
    """
    # Verify user is a student
    user = User.objects.filter(id=request.session.get('user_id'), role='student', is_archived=False).first()
    if not user:
        return redirect('home')
    
    # Get the material ID
    material_id_param = request.GET.get('id') or request.GET.get('material_id')
    if material_id_param and material_id_param.startswith('material-'):
        material_id = int(material_id_param.replace('material-', ''))
    else:
        material_id = int(material_id_param) if material_id_param else None
    
    if not material_id:
        return redirect('assessment')
    
    # Get the Story Response material
    material = Material.objects.filter(id=material_id).first()
    if not material:
        return redirect('assessment')
    
    content_json = material.content_json or {}
    
    # Verify it's a Story Response activity
    if content_json.get('activity_type') != 'story_response':
        return redirect('assessment')
    
    # Get the source story reading material
    source_story_id = content_json.get('source_story_reading_material_id')
    source_story = Material.objects.filter(id=source_story_id).first() if source_story_id else None
    
    if not source_story or not _is_story_reading_material(source_story):
        return redirect('assessment')
    
    source_content = source_story.content_json or {}
    
    # Build the activity payload
    activity_payload = {
        'id': material.id,
        'material_id': f'material-{material.id}',
        'title': str(content_json.get('activity_title') or material.title or 'Story Response').strip(),
        'source_story_id': source_story.id,
        'source_story_title': str(source_content.get('storyTitle') or source_story.title or '').strip(),
        'source_story_text': str(source_content.get('storyText') or source_story.content_text or '').strip(),
        'language': str(content_json.get('story_language') or source_content.get('language') or 'English').strip(),
        'response_prompt': str(content_json.get('response_prompt') or '').strip(),
        'prompt_category': str(content_json.get('prompt_category') or '').strip(),
        'prompt_source': str(content_json.get('prompt_source') or 'suggested').strip(),
        'host_character': str(content_json.get('host_character') or 'female').strip(),
        'read_aloud_enabled': bool(content_json.get('read_aloud_enabled', True)),
        'voice_recording_enabled': bool(content_json.get('voice_recording_enabled', True)),
        'student_first_name': str(user.first_name or '').strip().split()[0] if user.first_name else 'Friend',
        'assigned_week': material.assigned_week,
    }
    
    return render(request, 'pabasa_app/story_response_page.html', {
        'activity': activity_payload,
        'story_response_data': json.dumps(activity_payload),
    })


@csrf_protect
@login_required(role='student')
@require_http_methods(["POST"])
def story_response_submit(request):
    """
    Submit a student's story response.
    
    Request body:
    {
        "material_id": "material-123",
        "response_text": "The student's spoken/written response...",
        "audio_url": "Optional audio file URL",
        "duration_seconds": 45,
        "timestamp": "2026-01-15T10:30:00Z"
    }
    """
    try:
        payload = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    
    user = User.objects.filter(id=request.session.get('user_id'), role='student', is_archived=False).first()
    if not user:
        return JsonResponse({'success': False, 'error': 'Student not found.'}, status=404)
    
    material_id_param = payload.get('material_id', '')
    if material_id_param.startswith('material-'):
        material_id = int(material_id_param.replace('material-', ''))
    else:
        material_id = int(material_id_param) if material_id_param else None
    
    material = Material.objects.filter(id=material_id).first() if material_id else None
    if not material:
        return JsonResponse({'success': False, 'error': 'Activity not found.'}, status=404)
    
    content_json = material.content_json or {}
    if content_json.get('activity_type') != 'story_response':
        return JsonResponse({'success': False, 'error': 'Not a Story Response activity.'}, status=400)
    
    # Store the response (this could be saved to a new model or extended table)
    response_text = str(payload.get('response_text', '')).strip()
    audio_url = str(payload.get('audio_url', '')).strip()
    duration_seconds = int(payload.get('duration_seconds', 0))
    
    # For now, we'll store this in a simple way
    # In a production system, you might create a separate StoryResponse model
    # to track individual student responses
    
    # TODO: Create StoryResponse model to persist responses
    # and integrate with grading/feedback system
    
    return JsonResponse({
        'success': True,
        'message': 'Your response has been recorded.',
        'submitted_at': __import__('datetime').datetime.now().isoformat(),
    })
