import csv
import io
import distutils.util
import datetime

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.core.cache import cache

from utils import setting_handler
from plugins.consortial_billing import models, logic, plugin_settings, forms, security
from core import models as core_models

@security.billing_agent_required
def index(request):
    if request.POST:
        # an action
        if 'csv_upload' in request.FILES:
            csv_import = request.FILES['csv_upload']
            csv_reader = csv.DictReader(io.StringIO(csv_import.read().decode('utf-8')))

            for row in csv_reader:
                # get the band
                band, created = models.Banding.objects.get_or_create(name=row["Banding"])

                if distutils.util.strtobool(row["Consortial Billing"]):
                    consortium, created = models.Institution.objects.get_or_create(name=row["Consortium"])
                else:
                    consortium = None

                if row["Billing Agent"] != '':
                    billing_agent, created = models.BillingAgent.objects.get_or_create(name=row["Billing Agent"])
                else:
                    billing_agent = None

                institution, created = models.Institution.objects.get_or_create(name=row["Institution Name"],
                                                                                country=row["Country"],
                                                                                active=row["Active"],
                                                                                consortial_billing=
                                                                                row["Consortial Billing"],
                                                                                consortium=consortium,
                                                                                banding=band,
                                                                                billing_agent=billing_agent)

                dict_renewal_amount = row.get("Renewal Amount")
                renewal_amount = dict_renewal_amount if dict_renewal_amount != '' else 0.00

                renewal = models.Renewal.objects.create(date=row["Renewal Date"],
                                                        amount=renewal_amount,
                                                        institution=institution,
                                                        currency=row["Currency"])


    agent_for = logic.get_users_agencies(request)
    near_renewals, renewals_in_next_year, institutions = logic.get_institutions_and_renewals(agent_for)

    context = {'institutions': institutions,
               'renewals': near_renewals,
               'renewals_in_year': renewals_in_next_year,
               'plugin': plugin_settings.SHORT_NAME,
               'polls': models.Poll.objects.all()}

    return render(request, 'consortial_billing/admin.html', context)


def signup(request):
    signup_text = setting_handler.get_plugin_setting(plugin_settings.get_self(), 'preface_text', None)

    context = {'signup_text': signup_text}

    return render(request, 'consortial_billing/signup.html', context)


def signup_stage_two(request):
    bandings = models.Banding.objects.all().order_by('name', '-default_price')
    errors = list()

    if request.POST:
        banding_id = request.POST.get('banding')
        if banding_id:
            banding = get_object_or_404(models.Banding, pk=banding_id)
            return redirect(reverse('consortial_detail', kwargs={'banding_id': banding.pk}))
        else:
            banding = None
            errors.append('No banding has been selected')


    context = {
        'bandings': bandings,
        'errors': errors,
    }

    return render(request, 'consortial_billing/signup2.html', context)


def signup_complete(request):
    complete_text = setting_handler.get_plugin_setting(plugin_settings.get_self(), 'complete_text', None)

    context = {'complete_text': complete_text}

    return render(request, 'consortial_billing/complete.html', context)

def signup_stage_three(request, banding_id):
    banding = get_object_or_404(models.Banding, pk=banding_id)
    form = forms.Institution()

    if request.POST:
        form = forms.Institution(request.POST)
        if form.is_valid():
            institution = form.save(commit=False)
            institution.banding = banding
            institution.save()

            models.Renewal.objects.create(institution=institution,
                                          currency=banding.currency,
                                          amount=banding.default_price,
                                          date=timezone.now())

            logic.send_emails(institution, request)
            return redirect(reverse('consortial_complete'))


    context = {
        'banding': banding,
        'form': form,
    }

    return render(request, 'consortial_billing/signup3.html', context)


@staff_member_required
def non_funding_author_insts(request):
    if request.POST and 'user' in request.POST:
        user_id = request.POST.get('user')
        user = get_object_or_404(core_models.Account, pk=user_id)
        models.ExcludedUser.objects.get_or_create(user=user)
        messages.add_message(request, messages.INFO, "User has been excluded from this list.")
        return redirect(reverse('consortial_non_funding_author_insts'))

    institutions = models.Institution.objects.all()
    authors = logic.get_authors()
    editors = logic.get_editors()

    list_of_users_not_supporting = logic.users_not_supporting(institutions, authors, editors)

    template = 'consortial_billing/non_funding.html'
    context = {
        'authors_and_editors': list_of_users_not_supporting,
        'institutions': institutions,
    }

    return render(request, template, context)


def supporters(request):
    institutions = models.Institution.objects.filter(display=True)

    plugin = plugin_settings.get_self()
    pre_text = setting_handler.get_plugin_setting(plugin, 'pre_text', None)
    post_text = setting_handler.get_plugin_setting(plugin, 'post_text', None)

    template = 'consortial_billing/supporters.html'
    context = {
        'institutions': institutions,
        'pre_text': pre_text,
        'post_text': post_text
    }

    return render(request, template, context)


@security.billing_agent_required
def process_renewal(request, renewal_id):
    renewal = get_object_or_404(models.Renewal, pk=renewal_id, billing_complete=False)
    renewal_form = forms.Renewal(institution=renewal.institution)

    if request.POST:
        renewal_form = forms.Renewal(request.POST)
        if renewal_form.is_valid():
            new_renewal = renewal_form.save(commit=False)
            new_renewal.institution = renewal.institution
            renewal.billing_complete = True
            renewal.date_renewed = timezone.now()

            new_renewal.save()
            renewal.save()
            cache.clear()

            messages.add_message(request, messages.SUCCESS, 'Renewal for {0} processed.'.format(renewal.institution))
            return redirect(reverse('consortial_index'))

    context = {
        'renewal': renewal,
        'renewal_form': renewal_form,
    }

    return render(request, 'consortial_billing/process_renewal.html', context)


@staff_member_required
def view_renewals_report(request, start_date=None, end_date=None):
    if request.POST:
        start = request.POST.get('start')
        end = request.POST.get('end')
        print(start)
        return redirect(reverse('consortial_renewals_with_date', kwargs={'start_date': start, 'end_date': end}))

    if not start_date:
        start_date = timezone.now() - datetime.timedelta(days=365)

    if not end_date:
        end_date = timezone.now()

    renewals = models.Renewal.objects.filter(billing_complete=True,
                                             date_renewed__gte=start_date,
                                             date_renewed__lte=end_date)

    template = 'consortial_billing/renewals_report.html'
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'renewals': renewals,
    }

    return render(request, template, context)


@security.billing_agent_for_institution_required
def institution_manager(request, institution_id=None):
    if institution_id:
        institution = get_object_or_404(models.Institution, pk=institution_id)
        form = forms.InstitutionForm(instance=institution)
    else:
        institution = None
        form = forms.InstitutionForm()

    if request.POST:
        if institution_id:
            form = forms.InstitutionForm(request.POST, instance=institution)
        else:
            form = forms.InstitutionForm(request.POST)
            cache.clear()

        if form.is_valid():
            institution = form.save()
            if not institution_id:
                models.Renewal.objects.create(institution=institution,
                                              currency=institution.currency,
                                              amount=institution.default_price,
                                              date=timezone.now())

            messages.add_message(request, messages.SUCCESS, '{0} has been saved.'.format(institution.name))
            return redirect(reverse('consortial_index'))

    template = 'consortial_billing/institution_manager.html'
    context = {
        'institution': institution,
        'form': form,
    }

    return render(request, template, context)


@security.agent_for_billing_agent_required
def renewals_by_agent(request, billing_agent_id):
    billing_agent = get_object_or_404(models.BillingAgent, pk=billing_agent_id)
    renewals = models.Renewal.objects.filter(institution__billing_agent=billing_agent, billing_complete=False)

    if request.POST and 'mass_renewal' in request.POST:
        agent_id = request.POST.get('mass_renewal')
        if int(agent_id) == billing_agent.pk:
            logic.complete_all_renewals(renewals)
            messages.add_message(request, messages.SUCCESS, "{0} renewals completed".format(len(renewals)))
            cache.clear()
            return redirect(reverse('consortial_index'))

    template = 'consortial_billing/renewals_by_agent.html'
    context = {
        'billing_agent': billing_agent,
        'renewals': renewals,
    }

    return render(request, template, context)


@staff_member_required
def polling_manager(request, poll_id=None, option_id=None):
    if poll_id:
        poll = get_object_or_404(models.Poll, pk=poll_id)
        vote_count, all_count = logic.vote_count(poll)
    else:
        poll, vote_count, all_count = None, None, None

    if option_id:
        option = get_object_or_404(models.Option, pk=option_id)
    else:
        option = None

    bandings =  models.Banding.objects.all()

    form = forms.Poll(instance=poll)
    option_form = forms.Option(instance=option)
    banding_form = forms.Banding(option=option)

    if request.POST and 'poll' in request.POST:
        form = forms.Poll(request.POST, instance=poll)
        if form.is_valid():
            new_poll = form.save(commit=False)
            new_poll.staffer = request.user
            new_poll.save()
            messages.add_message(request, messages.INFO, 'Poll saved.')
            return redirect(reverse('consortial_polling_id', kwargs={'poll_id': new_poll.pk}))

    if request.POST and 'option' in request.POST:
        option_form = forms.Option(request.POST, instance=option)
        banding_form = forms.Banding(request.POST, option=option)

        if option_form.is_valid() and banding_form.is_valid():
            new_option = option_form.save()
            poll.options.add(new_option)
            banding_form.save(option=new_option)
            return redirect(reverse('consortial_polling_id', kwargs={'poll_id': poll.pk}))


    template = 'consortial_billing/polling_manager.html'
    context = {
        'form': form,
        'poll': poll,
        'bandings': bandings,
        'option': option,
        'option_form': option_form,
        'banding_form': banding_form,
        'vote_count': vote_count,
        'all_count': all_count,
    }

    return render(request, template, context)


def polls(request):
    polls = models.Poll.objects.filter(
        date_open__lte=timezone.now(),
        date_close__gte=timezone.now()
    )

    if request.POST:
        institution, poll, complete = logic.handle_polls_post(request, polls)

        if not institution:
            messages.add_message(request, messages.WARNING, 'No institution with that email address found.')
            return redirect(reverse('consortial_polls'))
        elif not poll:
            messages.add_message(request, messages.WARNING, 'No active poll with that ID found.')
            return redirect(reverse('consortial_polls'))
        elif complete:
            messages.add_message(request, messages.WARNING, 'Institution with that email address has already voted.')
            return redirect(reverse('consortial_polls'))
        else:
            logic.assign_cookie_for_vote(request, poll.pk, institution.pk)
            return redirect(reverse('consortial_polls_vote', kwargs={'poll_id': poll.pk}))

    template = 'consortial_billing/polls.html'
    context = {
        'polls': polls,
    }

    return render(request, template, context)


def polls_vote(request, poll_id):
    poll, institution, complete = logic.get_inst_and_poll_from_session(request)

    if not poll or not institution or complete:
        messages.add_message(request, messages.WARNING, 'You do not have permission to access this poll.')
        return redirect(reverse('consortial_polls'))

    if request.POST:
        voting = request.POST.getlist('options')
        aye_options = poll.options.filter(pk__in=voting)
        no_options = poll.options.exclude(pk__in=voting)

        vote = models.Vote.objects.create(institution=institution,
                                          poll=poll)
        vote.aye.add(*aye_options)
        vote.no.add(*no_options)
        vote.save()

        request.session['consortial_voting'] = None
        request.session.modified = True

        messages.add_message(request, messages.SUCCESS, 'Thank you for voting')
        return redirect(reverse('consortial_polls'))

    template = 'consortial_billing/polls_vote.html'
    context = {
        'institution': institution,
        'poll': poll,
    }

    return render(request, template, context)

