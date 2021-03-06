import re
import datetime
import csv
import os
from decimal import Decimal

from django.utils import timezone
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.conf import settings

from plugins.consortial_billing import models, plugin_settings, templatetags
from submission import models as submission_models
from core import models as core_models, files
from utils import notify_helpers, function_cache, setting_handler, render_template


def get_authors():
    authors = list()
    excluded_users = [user.user for user in models.ExcludedUser.objects.all()]
    articles = submission_models.Article.objects.filter(stage=submission_models.STAGE_PUBLISHED)

    for article in articles:
        for author in article.authors.all():
            if author not in excluded_users:
                authors.append(author)

    return authors


def get_editors():
    editors = list()
    excluded_users = [user.user for user in models.ExcludedUser.objects.all()]
    editorial_groups = core_models.EditorialGroup.objects.all()

    for group in editorial_groups:
        for member in group.members():
            if member.user not in excluded_users:
                editors.append(member.user)

    return editors


def users_not_supporting(institutions, authors, editors):

    authors_and_editors = list(set(authors + editors))
    institution_names = [inst.name for inst in institutions]

    authors_and_editors_output = list(set(authors + editors))

    print(institution_names)

    for user in authors_and_editors:
        find = re.compile(".*?{0}.*".format(user.institution.split(',')[0]))
        if len(list(filter(find.match, institution_names))) > 0:
            authors_and_editors_output.remove(user)

    return authors_and_editors_output


def get_signup_email_content(request, institution, currency, amount, host, url, display, user):
    plugin = plugin_settings.get_self()
    context = {'institution': institution, 'currency': currency, 'amount': amount, 'host': host, 'url': url,
               'display': display, 'user': user}

    return render_template.get_message_content(request, context, 'new_signup_email', plugin=plugin)


def send_emails(institution, currency, amount, display, request):

    if institution.banding.billing_agent:
        users = [user for user in institution.banding.billing_agent.users.all()]
        users = users + [user for user in core_models.Account.objects.filter(is_superuser=True)]

        if request.journal:
            host = request.journal_base_url
        else:
            host = request.press_base_url

        url = reverse('consortial_institution_id', kwargs={'institution_id': institution.pk})

        for user in users:
            message = get_signup_email_content(request, institution, currency, amount, host, url, display, user)
            notify_helpers.send_email_with_body_from_user(request,
                                                          'New Supporting Institution for {0}'.format(request.press.name),
                                                          user.email, message)


def get_users_agencies(request):
    if request.user.is_staff:
        return models.BillingAgent.objects.all()
    else:
        return models.BillingAgent.objects.filter(users__id__exact=request.user.pk)


@function_cache.cache(120)
def get_institutions_and_renewals(is_staff, user):
    if is_staff:
        near_renewals = models.Renewal.objects.filter(date__lte=timezone.now().date() + datetime.timedelta(days=31),
                                                      institution__active=True,
                                                      billing_complete=False).order_by('date')
        renewals_in_next_year = models.Renewal.objects.filter(
            date__lte=timezone.now().date() + datetime.timedelta(days=365),
            institution__active=True,
            billing_complete=False).values('currency').annotate(price=Sum('amount'))
        institutions = models.Institution.objects.all()
    else:
        agent_for = models.BillingAgent.objects.filter(users__id__exact=user.pk)
        near_renewals = models.Renewal.objects.filter(date__lte=timezone.now().date() + datetime.timedelta(days=31),
                                                      institution__active=True,
                                                      institution__billing_agent__in=agent_for,
                                                      billing_complete=False).order_by('date')

        renewals_in_next_year = models.Renewal.objects.filter(
            date__lte=timezone.now().date() + datetime.timedelta(days=365),
            institution__active=True,
            institution__billing_agent__in=agent_for,
            billing_complete=False).values('currency').annotate(price=Sum('amount'))
        institutions = models.Institution.objects.filter(billing_agent__in=agent_for)

    return near_renewals, renewals_in_next_year, institutions


def complete_all_renewals(renewals):
    renewal_date = timezone.now() + datetime.timedelta(days=334)

    for renewal in renewals:
        new_renewal = models.Renewal(date=renewal_date,
                                     amount=renewal.institution.banding.default_price,
                                     currency=renewal.institution.banding.currency,
                                     institution=renewal.institution)
        renewal.billing_complete = True
        renewal.date_renewed = timezone.now()

        new_renewal.save()
        renewal.save()


def handle_polls_post(request, polls):

    poll_id = request.POST.get('poll')
    email = request.POST.get('email')

    poll = get_object_or_404(models.Poll, pk=poll_id,
                             date_open__lte=timezone.now(),
                             date_close__gte=timezone.now()
                             )

    try:
        institution = models.Institution.objects.get(email_address__iexact=email)
    except (models.Institution.DoesNotExist, models.Institution.MultipleObjectsReturned):
        institution = None

    print(institution)

    try:
        vote = models.Vote.objects.filter(poll=poll, institution=institution)
    except models.Vote.DoesNotExist:
        vote = False

    return institution, poll, vote


def assign_cookie_for_vote(request, poll_id, institution_id):
    request.session['consortial_voting'] = {'poll': poll_id, 'institution': institution_id}
    request.session.modified = True


def get_inst_and_poll_from_session(request):
    if request.session.get('consortial_voting', None):
        poll_id = request.session['consortial_voting'].get('poll')
        institution_id = request.session['consortial_voting'].get('institution')

        poll = models.Poll.objects.get(pk=poll_id)
        inst = models.Institution.objects.get(pk=institution_id)

        try:
            vote = models.Vote.objects.filter(poll=poll, institution=inst)
        except models.Vote.DoesNotExist:
            vote = False

        return poll, inst, vote

    else:
        return None, None, False


def vote_count(poll):
    votes = models.Vote.objects.filter(poll=poll)
    vote_list = list()
    all_count = 0
    no_count = 0

    for option in poll.options.all():
        count = 0
        for vote in votes:
            if option in vote.aye.all():
                count = count + 1

        _dict = {
            'text': option.text,
            'count': count,
            'option': option,
        }

        vote_list.append(_dict)

        if option.all:
            all_count = all_count + count

    for vote in votes:
        if vote.aye.all().count() == 0:
            no_count += 1

    for _dict in vote_list:
        if _dict['count'] + all_count > votes.count() / 2:
            _dict['carried'] = True
        else:
            _dict['carried'] = False

    return vote_list, all_count, no_count


def process_poll_increases(options):
    renewals = models.Renewal.objects.filter(billing_complete=False)
    bandings = models.Banding.objects.all()

    for option in options:
        for renewal in renewals:
            banding = renewal.institution.banding

            if banding:
                increase = models.IncreaseOptionBand.objects.get(option=option, banding=banding)
                print("Increasing renewal for {0} [Band {1}] by {2} {3} for option {4}".format(renewal.institution,
                                                                                               renewal.institution.banding.name,
                                                                                               increase.price_increase,
                                                                                               renewal.institution.banding.currency,
                                                                                               option.text))
                renewal.amount = float(renewal.amount) + float(increase.price_increase)
                renewal.save()

        for banding in bandings:
            increase = models.IncreaseOptionBand.objects.get(option=option, banding=banding)
            print("Increasing banding {0} by {1} {2} for option {3}".format(banding.name,
                                                                            banding.currency,
                                                                            increase.price_increase,
                                                                            option.text))
            banding.default_price = float(banding.default_price) + float(increase.price_increase)
            banding.save()


def get_poll_email_content(request, poll, institution):
    plugin = plugin_settings.get_self()
    short_name = setting_handler.get_plugin_setting(plugin, 'organisation_short_name', None).value
    context = {'poll': poll, 'institution': institution, 'short_name': short_name}

    return render_template.get_message_content(request, context, 'email_text', plugin=plugin)


def email_poll_to_institutions(poll, request):
    institutions = models.Institution.objects.filter(email_address__isnull=False)

    for institution in institutions:
        content = get_poll_email_content(request, poll, institution)
        notify_helpers.send_email_with_body_from_user(request,
                                                      'New Consortium Poll',
                                                      institution.email_address,
                                                      content)


@function_cache.cache(120)
def get_model_renewals(institutions):

    projected_currency = {}

    for institution in institutions:
        if projected_currency.get(institution.banding.currency):
            projected_currency[institution.banding.currency] = projected_currency[institution.banding.currency] + \
                templatetags.currency.convert_multiplier(
                value=institution.banding.default_price,
                currency=institution.banding.currency,
                multiplier=institution.multiplier
            )
        else:
            projected_currency[institution.banding.currency] = templatetags.currency.convert_multiplier(
                value=institution.banding.default_price,
                currency=institution.banding.currency,
                multiplier=institution.multiplier
            )

    total = 0
    for k, v in projected_currency.items():
        total = total + v

    projected_currency['total'] = total

    return projected_currency


def count_renewals_by_month(year):
    from plugins.consortial_billing.templatetags.currency import convert
    renewals = models.Renewal.objects.filter(date__year=year)
    by_month = dict()

    for renewal in renewals:
        gbp_amount = convert(renewal.amount, renewal.currency, action='number')

        if by_month.get(renewal.date.month, None):
            by_month[renewal.date.month] = by_month[renewal.date.month] + float(gbp_amount)
        else:
            by_month[renewal.date.month] = float(gbp_amount)

    for x in range(1, 13):
        if not by_month.get(x, None):
            by_month[x] = 0.00

    return by_month


def get_total_revenue(revenue_by_month):
    total = 0.00

    for k, v in revenue_by_month.items():
        total = total + v

    return total


def serve_csv_file(revenue_by_month):
    filename = '{0}.csv'.format(datetime.datetime.now())
    full_path = os.path.join(settings.BASE_DIR, 'files', 'temp', filename)
    with open(full_path, 'w') as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=',')

        for month, value in revenue_by_month.items():
            csv_writer.writerow([month, value])

    return files.serve_temp_file(full_path, filename)


def calc_discount(value, discount):
    discount = round(float(value) - (float(value) * float(discount) / 100), 2)
    return discount


def record_referral(referent, institution, referent_discount):
    discount = setting_handler.get_plugin_setting(plugin_settings.get_self(), 'referrer_discount', None).value
    referring_institution = models.Institution.objects.get(referral_code=referent)
    new_rate = calc_discount(referring_institution.next_renewal.amount, discount)

    if new_rate < 0:
        new_rate = 0

    referring_institution.next_renewal.amount = new_rate
    referring_institution.next_renewal.save()

    renewal = models.Renewal.objects.get(pk=referring_institution.next_renewal.pk)
    referrer_discount = float(renewal.amount) - float(new_rate)
    renewal.amount = new_rate
    renewal.save()

    referral = models.Referral.objects.create(referring_institution=referring_institution,
                                              new_institution=institution,
                                              referring_discount=referrer_discount,
                                              referent_discount=referent_discount)

    return referral
