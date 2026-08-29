#!/usr/bin/env python
"""
Letter & Sound Matching Audio Pipeline Test Script
Tests the complete audio pipeline from phonics item to file availability
"""

import os
import sys
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')

# Add project to path
project_root = Path(__file__).parent / 'pabasa_site'
sys.path.insert(0, str(project_root.parent))

import django
django.setup()

from pabasa_app.models import ReadingMaterial, ReadingSet
from django.conf import settings

def test_audio_files():
    """Verify all audio files exist for phonics items"""
    print("\n" + "="*70)
    print("LETTER & SOUND MATCHING - AUDIO PIPELINE TEST")
    print("="*70)
    
    # Test Filipino phonics
    print("\n📝 Testing Filipino Phonics Audio Files")
    print("-" * 70)
    
    test_cases_fil = [
        # Vowels
        ("A", "vowels", "Filipino"),
        ("E", "vowels", "Filipino"),
        ("I", "vowels", "Filipino"),
        ("O", "vowels", "Filipino"),
        ("U", "vowels", "Filipino"),
        # Syllables
        ("MA", "syllables", "Filipino"),
        ("BA", "syllables", "Filipino"),
        ("TA", "syllables", "Filipino"),
        ("YU", "syllables", "Filipino"),
        ("NGA", "syllables", "Filipino"),
        ("ÑA", "syllables", "Filipino"),
    ]
    
    test_audio_files_list(test_cases_fil)
    
    # Test English phonics
    print("\n📝 Testing English Phonics Audio Files")
    print("-" * 70)
    
    test_cases_eng = [
        # Vowels
        ("A", "vowels", "English"),
        ("E", "vowels", "English"),
        ("I", "vowels", "English"),
        ("O", "vowels", "English"),
        ("U", "vowels", "English"),
        # Syllables
        ("CH", "syllables", "English"),
        ("SH", "syllables", "English"),
        ("TH", "syllables", "English"),
        ("AI", "syllables", "English"),
        ("NG", "syllables", "English"),
    ]
    
    test_audio_files_list(test_cases_eng)
    
    # Test Letter & Sound Matching material detection
    print("\n" + "="*70)
    print("Testing Material Detection")
    print("="*70)
    
    try:
        materials = ReadingMaterial.objects.filter(
            template_activity_name__icontains='letter'
        ) | ReadingMaterial.objects.filter(
            activity_type__icontains='letter'
        )
        
        if materials.exists():
            print(f"\n✅ Found {materials.count()} Letter & Sound Matching materials:")
            for material in materials[:5]:
                print(f"  - {material.title} (ID: {material.id})")
                print(f"    Template: {material.template_activity_name}")
                print(f"    Type: {material.activity_type}")
        else:
            print("\n⚠️  No Letter & Sound Matching materials found in database")
            print("    This is expected if using reading sets from courses.html")
    except Exception as e:
        print(f"\n❌ Error querying materials: {e}")
    
    # Test reading sets
    print("\n" + "="*70)
    print("Testing Reading Sets")
    print("="*70)
    
    test_reading_sets()
    
    print("\n" + "="*70)
    print("AUDIO PIPELINE TEST COMPLETE")
    print("="*70 + "\n")


def test_audio_files_list(test_cases):
    """Test a list of phonics audio files"""
    static_root = Path(settings.BASE_DIR) / 'pabasa_app' / 'static'
    passed = 0
    failed = 0
    
    for phonics, category, language in test_cases:
        lang_folder = language.lower()
        lang_code = 'T' if language.lower().startswith('fil') else 'E'
        filename = f"{phonics} ({lang_code}).MP3"
        filepath = static_root / 'pabasa_app' / 'audio' / 'phonics' / lang_folder / category / filename
        
        if filepath.exists():
            print(f"  ✅ {phonics:4} ({lang_code}) - {category:10} - Found")
            passed += 1
        else:
            print(f"  ❌ {phonics:4} ({lang_code}) - {category:10} - NOT FOUND")
            print(f"     Expected: {filepath}")
            failed += 1
    
    print(f"\nResult: {passed} passed, {failed} failed")
    return passed, failed


def test_reading_sets():
    """Test reading sets with phonics items"""
    try:
        reading_sets = ReadingSet.objects.all()[:10]
        if reading_sets.exists():
            print(f"\nFound {ReadingSet.objects.count()} reading sets:")
            for rs in reading_sets:
                print(f"  - {rs.name} (ID: {rs.id})")
                if rs.content:
                    try:
                        # Try to parse content as JSON
                        import json
                        content = json.loads(rs.content) if isinstance(rs.content, str) else rs.content
                        if isinstance(content, dict) and 'items' in content:
                            items = content['items']
                            print(f"    Items: {len(items)} phonics")
                            if items:
                                print(f"    Sample: {items[0]}")
                    except:
                        print(f"    Content: {len(str(rs.content))} bytes")
        else:
            print("\n⚠️  No reading sets found")
    except Exception as e:
        print(f"\n❌ Error querying reading sets: {e}")


def test_django_settings():
    """Verify Django settings for static files"""
    print("\n" + "="*70)
    print("Django Settings Verification")
    print("="*70)
    
    print(f"\n✓ BASE_DIR: {settings.BASE_DIR}")
    print(f"✓ STATIC_URL: {settings.STATIC_URL}")
    print(f"✓ STATIC_ROOT: {settings.STATIC_ROOT}")
    print(f"✓ DEBUG: {settings.DEBUG}")
    
    # Check if static directories exist
    audio_dir = Path(settings.BASE_DIR) / 'pabasa_app' / 'static' / 'pabasa_app' / 'audio' / 'phonics'
    if audio_dir.exists():
        print(f"\n✅ Audio directory exists: {audio_dir}")
        
        # List subdirectories
        for lang_dir in audio_dir.iterdir():
            if lang_dir.is_dir():
                print(f"\n  Language: {lang_dir.name}")
                for cat_dir in lang_dir.iterdir():
                    if cat_dir.is_dir():
                        file_count = len(list(cat_dir.glob('*.MP3')))
                        print(f"    - {cat_dir.name}: {file_count} files")
    else:
        print(f"\n❌ Audio directory NOT found: {audio_dir}")


if __name__ == '__main__':
    test_django_settings()
    test_audio_files()
