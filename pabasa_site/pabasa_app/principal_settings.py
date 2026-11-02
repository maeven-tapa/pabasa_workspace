"""Self-service settings; school structure and calendar remain Admin managed."""
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.utils.dateparse import parse_datetime
from django.utils import timezone
import hashlib

from .models import User
from .principal_reporting import PrincipalScope
from .principal_security import validate_principal_password


class PersonalInformationForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    middle_initial = forms.CharField(max_length=1, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'middle_initial', 'email', 'contact_no']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This email address is already used by another account.')
        return email


def settings_context(request, user, context):
    from .views import _get_profile_dict, _notification_settings_for_user, _parse_user_agent
    if request.method == 'POST':
        action = request.POST.get('settings_action')
        if action in {'save_school_info', 'save_academic_year'}:
            return HttpResponseForbidden('School information and academic dates are managed by an Administrator.')
        if action == 'save_notifications':
            return HttpResponseForbidden('Principal school alerts are managed by the notification service.')
        if action == 'change_password':
            current = request.POST.get('current_password', '')
            password = request.POST.get('new_password', '')
            if not user.check_password(current):
                context['settings_error'] = 'Current password is incorrect.'
            elif password != request.POST.get('confirm_password', ''):
                context['settings_error'] = 'New passwords do not match.'
            elif password == current:
                context['settings_error'] = 'Choose a different private password.'
            else:
                try:
                    validate_principal_password(password, user)
                except ValidationError as exc:
                    context['settings_error'] = ' '.join(exc.messages)
                else:
                    user.set_password(password)
                    user.principal_password_expires_at = None
                    user.save(update_fields=['password_hash', 'principal_password_expires_at', 'updated_at'])
                    request.session['principal_password_version'] = hashlib.sha256(user.password_hash.encode()).hexdigest()
                    request.session.cycle_key()
                    context['settings_success'] = 'Password changed successfully.'
        elif action == 'save_personal_info':
            if any(key in request.POST for key in ('position', 'role', 'custom_id', 'pabasa_id', 'principal_id')):
                return HttpResponseForbidden('PABASA ID and role/position are managed by an Administrator.')
            data = request.POST.copy()
            data['contact_no'] = data.get('contact_number', '')
            form = PersonalInformationForm(data, instance=user)
            if not form.is_valid():
                context['settings_error'] = ' '.join(f'{field}: {" ".join(errors)}' for field, errors in form.errors.items())
            else:
                try:
                    with transaction.atomic():
                        form.save()
                except IntegrityError:
                    context['settings_error'] = 'This email address is already used by another account.'
                else:
                    for key in ('first_name', 'last_name', 'middle_initial', 'email'):
                        request.session[key] = getattr(user, key)
                    context['settings_success'] = 'Personal information updated.'
        else:
            context['settings_error'] = 'Unknown settings action.'
    scope = PrincipalScope.resolve(user)
    school = user.school_record
    profile = _get_profile_dict(user, 'principal_profile_info')
    profile = profile if isinstance(profile, dict) else {}
    login = parse_datetime(request.session.get('login_at', ''))
    context.update({
        'school_info': {'name': school.name if school else 'School not assigned', 'code': school.code if school else '',
                        'address': school.address if school else '', 'contact': school.contact_information if school else ''},
        'academic_settings': {'academic_year': scope.calendar.school_year if scope.calendar else 'Not configured',
                              'term': str(scope.calendar.current_term) if scope.calendar else '',
                              'school_year_start': scope.start.isoformat() if scope.start else '',
                              'school_year_end': scope.end.isoformat() if scope.end else ''},
        'principal_profile_info': profile, 'first_name': user.first_name, 'last_name': user.last_name,
        'middle_initial': user.middle_initial, 'email': user.email or '', 'contact_number': user.contact_no or '',
        'notification_settings': _notification_settings_for_user(user),
        'last_login': timezone.localtime(login).strftime('%B %d, %Y %I:%M %p') if login and timezone.is_aware(login) else 'Not recorded',
        'account_created': user.created_at.strftime('%B %d, %Y'), 'browser_device': _parse_user_agent(request.META.get('HTTP_USER_AGENT', '')),
        'build_version': getattr(settings, 'PABASA_BUILD_VERSION', '') or 'Not supplied by deployment',
    })
    return context
