from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import course, schedule, subject, news
from user.models import UserInformation, Activation

# Use custom logout template for admin
admin.site.logout_template = 'registration/logout.html'


@admin.action(description=_('Activate selected courses'))
def activate_courses(modeladmin, request, queryset):
    """Fix for Issue #102: Mass-activation of courses"""
    queryset.update(active=True)


@admin.action(description=_('Deactivate selected courses'))
def deactivate_courses(modeladmin, request, queryset):
    """Fix for Issue #102: Mass-deactivation of courses"""
    queryset.update(active=False)
    # Clear participants when deactivating
    for course_obj in queryset:
        course_obj.participants.clear()


class CourseAdmin(admin.ModelAdmin):
    actions = [activate_courses, deactivate_courses]
    list_display = ['__str__', 'subject', 'active', 'visible', 'max_participants']
    list_filter = ['active', 'visible', 'subject']
    search_fields = ['subject__name']


class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_enrollments_per_user']
    list_editable = ['max_enrollments_per_user']
    fields = ['name', 'description', 'max_enrollments_per_user']
    help_texts = {
        'max_enrollments_per_user': 'Maximum number of courses in this subject a user can enroll in. 0 means unlimited.'
    }


admin.site.register(course.Course, CourseAdmin)
admin.site.register(course.Notification)
admin.site.register(course.Participation)
admin.site.register(schedule.Schedule)
admin.site.register(schedule.WeeklySlot)
admin.site.register(schedule.DateSlot)
admin.site.register(UserInformation)
admin.site.register(Activation)
admin.site.register(subject.Subject, SubjectAdmin)
admin.site.register(news.News)
