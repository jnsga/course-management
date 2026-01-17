from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.models import User
from django.urls import reverse
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from guardian.shortcuts import assign_perm
from guardian.shortcuts import remove_perm

from course.forms import CourseForm, AddTeacherForm, NotifyCourseForm, MoveStudentForm
from course.models.course import Course
from course.models.schedule import Schedule
from course.models.subject import Subject
from course.util.permissions import needs_teacher_permissions
from user.models import UserInformation
from user.forms import ContactForm
from util import html_clean
from util.error.reporting import db_error
from util.routing import redirect_unless_target
import itertools

DEFAULT_COURSE_DESCRIPTION = """\
#### The Hitchhikers Guide To The Galaxy

We will explore the universe.

##### Materials

- a towel
- lots of courage
"""

CONTACT_FOOTER = """
-------------------
This message has been sent via the Course Mangement System at https://kurse.ifsr.de.
Sent by: """

BLANK_FOOTER = """
-------------------
This message has been sent via the Course Mangement System at https://kurse.ifsr.de.
"""



def course(request: HttpRequest, course_id: str):
    """
    Controller for single course info page

    :param request: request object
    :param course_id: id for the course
    :return:
    """
    try:
        current_course = Course.objects.get(id=course_id)

        if hasattr(request.user, 'userinformation'):
            user = request.user.userinformation

            if isinstance(user, UserInformation):
                context = current_course.as_context(user)
            else:
                context = current_course.as_context()
        else:
            context = current_course.as_context()

        session = request.session
        if 'enroll-error' in session:
            context['error'] = session['enroll-error']
            del session['enroll-error']

        return render(
            request,
            'course/info.html',
            context
        )
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))


@needs_teacher_permissions
def participants_list(request, course_id):
    try:
        current_course = Course.objects.get(id=course_id)

        return render(
            request,
            'course/attendees.html',
            {'course': current_course}
        )
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))


@needs_teacher_permissions
def edit_course(request: HttpRequest, course_id: str):
    """
    Edit form for changing a course and handler for submitted data.

    :param request: request object
    :param course_id: id for the course
    :return:
    """
    try:
        current_course = Course.objects.get(id=course_id)
        current_schedule = Schedule.objects.get(course_id=course_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))

    if request.method == "POST":
        form = CourseForm(request.POST, instance=current_course)

        if form.is_valid():
            current_course.save()
            # Safely get schedule_type from POST data
            schedule_type = request.POST.get('schedule_type', 'W')
            if schedule_type in ['W', 'O']:  # Validate allowed values
                current_schedule.set_type(schedule_type)
                current_schedule.save()
            return redirect('course', course_id)

    else:
        # FIXME(feliix42): Manually setting the start & end date here is required beacuse I just can't get django to format the date correctly in the Form setup
        form = CourseForm(instance=current_course,initial={
            'schedule_type':current_schedule.get_type(),
            'start_time': current_course.start_time.strftime('%Y-%m-%d'),
            'end_time': current_course.end_time.strftime('%Y-%m-%d')
        })
    return render(
        request,
        'course/edit.html',
        {
            'title': _('Edit course'),
            'form': form,
            'create': False,
            'course_id': course_id,
            'allowed_tags': html_clean.DESCR_ALLOWED_TAGS,
            'course_is_active': current_course.active,
        }
    )


@needs_teacher_permissions
@require_POST
def toggle(request: HttpRequest, course_id: str, active: bool):
    """
    Toggle course status (active/inactive)

    :param request: request information
    :param course_id:
    :param active: active/inactive
    :return:
    """
    # TODO: Delete me
    try:
        curr_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))

    curr_course.active = active
    if not active:
        curr_course.participants.clear()
        curr_course.queue.clear()
    curr_course.save()
    return redirect('course', course_id)


@permission_required('course.add_course')
def create(request):

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            created = form.save(commit=False)
            created.save()
            created.teacher.add(request.user.userinformation)

            # Safely get schedule_type from POST data
            schedule_type = request.POST.get('schedule_type', 'W')
            if schedule_type not in ['W', 'O']:  # Validate allowed values
                schedule_type = 'W'
            Schedule.objects.create(_type=schedule_type, course=created)

            assign_perm(
                'change_course',
                request.user,
                created
            )
            assign_perm(
                'delete_course',
                request.user,
                created
            )

            return redirect('course', created.id)
    else:
        form = CourseForm(initial={
            'description': DEFAULT_COURSE_DESCRIPTION,
            'max_participants': 30,
            'archiving': 't'
        })
        if 'subject' in request.GET:
            try:
                # Safely get and validate subject ID
                subject_id = request.GET.get('subject', '')
                if subject_id:
                    # Handle both single value and list
                    subject_id = subject_id[0] if isinstance(subject_id, list) else subject_id
                    subj = int(subject_id)
                    if Subject.objects.filter(id=subj).exists():
                        form.initial['subject'] = subj
            except (ValueError, IndexError, TypeError):
                # Invalid subject ID, ignore
                pass

    return render(
        request,
        'course/edit.html',
        {
            'title': _('New Course'),
            'form': form,
            'create': True
        }
    )


@login_required()
@require_POST
@needs_teacher_permissions
def delete(request, course_id):
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))

    subj = course.subject.name

    course.delete()
    return redirect('subject', subj)


@needs_teacher_permissions
def add_teacher(request, course_id):
    context = {
        'title': _('Edit Teachers'),
        'course_id': course_id,
        'target': reverse('add-teacher', args=(course_id,))
    }

    try:
        curr_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))

    if request.method == 'POST':
        form = AddTeacherForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(username=form.cleaned_data['username'])

                curr_course.teacher.add(user.userinformation)
                assign_perm(
                    'change_course',
                    user,
                    curr_course
                )
                assign_perm(
                    'delete_course',
                    user,
                    curr_course
                )

                return redirect('add-teacher', course_id)
            except User.DoesNotExist:
                context['error'] = _('The username you entered does not exist.')
    else:
        form = AddTeacherForm()

    context['form'] = form
    context['teachers'] = curr_course.teacher

    return render(
        request,
        'course/teachers.html',
        context
    )


@needs_teacher_permissions
@require_POST
def remove_teacher(request, course_id, teacher_id):
    try:
        curr_course = Course.objects.get(id=course_id)
        userinfo = UserInformation.objects.get(id=teacher_id)
        curr_course.teacher.remove(userinfo)
        remove_perm(
            'change_course',
            userinfo.user,
            curr_course
        )
        remove_perm(
            'delete_course',
            userinfo.user,
            curr_course
        )
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))
    except UserInformation.DoesNotExist:
        return db_error(request, _('Requested student does not exist.'))
    return redirect_unless_target(request, 'course', course_id)


@needs_teacher_permissions
def notify(request: HttpRequest, course_id):
    if request.method == 'POST':
        form = NotifyCourseForm(request.POST)
        if form.is_valid():
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return db_error(request, _('Requested course does not exist.'))

            email = request.user.email
            show_sender = form.cleaned_data['show_sender'] and email

            if show_sender:
                content = form.content + CONTACT_FOOTER + email
            else:
                content = form.content + BLANK_FOOTER

            for student in itertools.chain(course.participants.all(), course.teacher.all()):
                student.user.email_user("[iFSR Course Manager] " + form.subject, content)

            return redirect('notify-course-done', course_id)

    else:
        form = NotifyCourseForm()

    return render(
        request,
        'course/notify.html',
        {
            'title': _('Notify Course'),
            'form': form,
            'course_id': course_id
        }
    )


def notify_done(request, course_id):
    return render(
        request,
        'course/notify-done.html',
        {
            'course_id': course_id
        }
    )


@needs_teacher_permissions
def remove_student(request: HttpRequest, course_id:str, student_id:str):
    try:
        course = Course.objects.get(id=course_id)
        course.unenroll(student_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))
    except Course.IsNotEnrolled:
        # Fix for Issue #112: Catch IsNotEnrolled exception
        return db_error(request, _('Requested student is not enrolled in this course.'))

    return redirect('course', course_id)


@login_required()
def move_student(request: HttpRequest, course_id: str, student_id: str):
    """
    Fix for Issue #66: Allow superusers to move students between courses.
    Only accessible to superusers.
    """
    # Check if user is superuser
    if not request.user.is_superuser:
        return db_error(request, _('Only superusers can move students between courses.'))
    
    try:
        source_course = Course.objects.get(id=course_id)
        student = UserInformation.objects.get(id=student_id)
    except Course.DoesNotExist:
        return db_error(request, _('Requested course does not exist.'))
    except UserInformation.DoesNotExist:
        return db_error(request, _('Requested student does not exist.'))
    
    # Check if student is enrolled in source course
    if not source_course.is_participant(student):
        return db_error(request, _('Student is not enrolled in the source course.'))
    
    if request.method == 'POST':
        form = MoveStudentForm(request.POST, exclude_course=source_course)
        if form.is_valid():
            target_course = form.cleaned_data['target_course']
            
            try:
                # Check if student is already enrolled in target course
                if target_course.is_participant(student):
                    return db_error(
                        request,
                        _('Student is already enrolled in the target course.')
                    )
                
                # Unenroll from source course
                source_course.unenroll(student)
                
                # Enroll in target course (bypass active check for superuser move)
                # We need to temporarily set active=True if it's not active
                was_active = target_course.active
                was_archived = target_course.is_archived()
                
                if not was_active:
                    target_course.active = True
                    target_course.save()
                
                try:
                    # Temporarily set archiving to 't' if archived, to allow enrollment
                    if was_archived:
                        original_archiving = target_course.archiving
                        target_course.archiving = 't'
                        target_course.save()
                    
                    target_course.enroll(student)
                except (Course.IsEnrolled, Course.IsInactive, Course.IsArchived) as e:
                    # If enrollment fails, re-enroll in source course
                    if not was_active:
                        target_course.active = False
                        target_course.save()
                    if was_archived:
                        target_course.archiving = original_archiving
                        target_course.save()
                    # Try to re-enroll in source course
                    try:
                        source_course.enroll(student)
                    except:
                        pass  # If this fails, at least we tried
                    return db_error(
                        request,
                        _('Failed to enroll student in target course. Student remains in source course.')
                    )
                finally:
                    # Restore original active state
                    if not was_active:
                        target_course.active = False
                        target_course.save()
                    if was_archived:
                        target_course.archiving = original_archiving
                        target_course.save()
                
                from django.contrib import messages
                messages.success(
                    request,
                    _('Student {} has been successfully moved from {} to {}.'.format(
                        student, source_course.subject.name, target_course.subject.name
                    ))
                )
                return redirect('course-participants', course_id)
            except Exception as e:
                return db_error(
                    request,
                    _('An error occurred while moving the student: {}').format(str(e))
                )
    else:
        form = MoveStudentForm(exclude_course=source_course)
    
    return render(
        request,
        'course/move-student.html',
        {
            'title': _('Move Student'),
            'form': form,
            'course': source_course,
            'student': student,
        }
    )


@needs_teacher_permissions
def attendee_list(request, course_id):
    if 'slots' in request.GET:
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return db_error(request, _('Requested course does not exist.'))

        # handle empty string (== no number) as input
        try:
            slots = int(request.GET['slots'])
        except ValueError:
            slots = 0

        # Fix for Issue #103: Only show enrolled participants, not waiting list
        # Get only the first max_participants participants (enrolled students)
        from course.models.course import Participation
        enrolled_participations = Participation.objects.filter(course=course).order_by('ticket_number')[:course.max_participants]
        enrolled_attendees = [p.participant for p in enrolled_participations]

        return render(
                request,
                'course/attendee-list.html',
                {
                    'attendees': enrolled_attendees,
                    'slots': range(slots)
                }
        )
    return redirect('course-participants', course_id)

def contact_teachers(request, course_id):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return db_error(request, _('Requested course does not exist.'))

            subject = "[CM contact form] " + form.subject
            content = form.content + CONTACT_FOOTER + request.user.email

            for teacher in course.teacher.all():
                teacher.user.email_user(subject, content)

            return redirect('contact-teachers-done', course_id)

    else:
        form = ContactForm()

    return render(
        request,
        'course/contact-teachers.html',
        {
            'title': _('Notify Course'),
            'form': form,
            'course_id': course_id
        }
    )
