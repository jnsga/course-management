from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from course.models.course import Course

from util.error.reporting import db_error
from util.routing import redirect_unless_target


@require_POST
@login_required()
def add(request, course_id):
    user = request.user
    stud = user.userinformation
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))
    session = request.session

    if course.is_participant(stud):
        session['enroll-error'] = _('You are already enrolled in this course.')
    else:
        # Fix for Issue #104: Check if user has reached max enrollments for this subject
        subject = course.subject
        if subject.max_enrollments_per_user > 0:
            # Count how many courses in this subject the user is enrolled in
            enrolled_count = sum(
                1 for c in subject.course_set.all()
                if c.is_participant(stud)
            )
            if enrolled_count >= subject.max_enrollments_per_user:
                session['enroll-error'] = _(
                    'You have reached the maximum number of enrollments ({}) '
                    'allowed for this subject.'.format(subject.max_enrollments_per_user)
                )
                return redirect_unless_target(request, 'course', course_id)
        
        if 'enroll-error' in session:
            del session['enroll-error']
        try:
            course.enroll(stud)
        except Course.IsInactive:
            return HttpResponseForbidden()
        except Course.IsArchived:
            return HttpResponseForbidden()

    # redirect to course overview or specified target
    return redirect_unless_target(request, 'course', course_id)


@require_POST
@login_required()
def remove(request, course_id):
    stud = request.user.userinformation
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))
    ps = course.participants

    if course.is_participant(stud):
        ps.remove(stud)
    else:
        request.session['enroll-error'] = _('You do not seem to be enrolled in this course.')
        return redirect('course', course_id)

    # redirect to course overview or specified target
    return redirect_unless_target(request, 'course', course_id)
