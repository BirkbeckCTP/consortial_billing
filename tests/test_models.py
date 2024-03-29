__copyright__ = "Copyright 2023 Birkbeck, University of London"
__author__ = "Open Library of Humanities"
__license__ = "AGPL v3"
__maintainer__ = "Open Library of Humanities"

from unittest.mock import patch, Mock
import decimal

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest

from plugins.consortial_billing import models, plugin_settings
from plugins.consortial_billing import utils
from utils.testing import helpers
from press import models as press_models
from cms.models import Page


class TestCaseWithData(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plugin_settings.install(fetch_data=False)
        cls.press = press_models.Press(domain="supporters.org")
        cls.press.save()
        cls.user_supporter = helpers.create_user('user_supporter@example.org')
        cls.user_supporter.is_active = True
        cls.user_supporter.save()
        cls.user_staff = helpers.create_user('user_billing_staff@example.org')
        cls.user_staff.is_staff = True
        cls.user_staff.is_active = True
        cls.user_staff.save()
        cls.user_agent = helpers.create_user('user_agent@example.org')
        cls.user_agent.is_active = True
        cls.user_agent.save()
        cls.agent_default = models.BillingAgent.objects.create(
            name='Open Library of Humanities',
            default=True,
        )
        cls.agent_default.save()
        models.AgentContact.objects.get_or_create(
            agent=cls.agent_default,
            account=cls.user_staff,
        )
        cls.agent_other = models.BillingAgent.objects.create(
            name='Diamond OA Association',
            country='BE',
            redirect_url='example.org'
        )
        cls.agent_other.save()
        models.AgentContact.objects.get_or_create(
            agent=cls.agent_other,
            account=cls.user_agent,
        )
        cls.size_base = models.SupporterSize.objects.create(
            name='Large',
            description='10,000+ students',
            multiplier=1,
        )
        cls.size_other = models.SupporterSize.objects.create(
            name='Small',
            description='0-4,999 students',
            multiplier=0.6,
        )
        cls.level_base = models.SupportLevel.objects.create(
            name='Standard',
            order=2,
            default=True,
        )
        cls.level_other = models.SupportLevel.objects.create(
            name='Higher',
            order=1,
        )
        cls.level_third = models.SupportLevel.objects.create(
            name='Even Higher',
            order=0,
        )
        cls.currency_base = models.Currency.objects.create(
            code='GBP',
            region='GBR',
            symbol='£',
        )
        cls.currency_other = models.Currency.objects.create(
            code='EUR',
            region='EMU',
            symbol='€',
        )
        cls.band_base = models.Band.objects.create(
            size=cls.size_base,
            country='GB',
            currency=cls.currency_base,
            level=cls.level_base,
            fee=1000,
            billing_agent=cls.agent_default,
            base=True,
        )
        cls.band_base_level_other = models.Band.objects.create(
            size=cls.size_base,
            country='GB',
            currency=cls.currency_base,
            level=cls.level_other,
            fee=5000,
            billing_agent=cls.agent_default,
            base=True,
        )
        cls.band_base_country_other = models.Band.objects.create(
            size=cls.size_other,
            country='DE',
            currency=cls.currency_other,
            level=cls.level_third,
            fee=5000,
            billing_agent=cls.agent_default,
            base=True,
        )
        cls.band_other_one = models.Band.objects.create(
            size=cls.size_base,
            country='GB',
            currency=cls.currency_base,
            level=cls.level_base,
            fee=1001,
            billing_agent=cls.agent_default,
        )
        cls.band_other_two = models.Band.objects.create(
            size=cls.size_other,
            country='BE',
            currency=cls.currency_other,
            level=cls.level_other,
            billing_agent=cls.agent_other,
            fee=2000,
            warnings='Oh no!'
        )
        cls.band_other_three = models.Band.objects.create(
            size=cls.size_base,
            country='GB',
            currency=cls.currency_base,
            level=cls.level_base,
            fee=1500,
            billing_agent=cls.agent_default,
        )
        cls.band_fixed_fee = models.Band.objects.create(
            size=cls.size_other,
            country='FR',
            currency=cls.currency_other,
            level=cls.level_other,
            fee=7777,
            fixed_fee=True,
            billing_agent=cls.agent_other,
        )
        cls.supporter_one = models.Supporter.objects.create(
            name='Birkbeck, University of London',
            ror='https://ror.org/02mb95055',
            band=cls.band_base,
            active=True,
        )
        cls.supporter_one.save()
        models.SupporterContact.objects.get_or_create(
            supporter=cls.supporter_one,
            account=cls.user_supporter,
        )
        cls.supporter_two = models.Supporter.objects.create(
            name='University of Sussex',
            band=cls.band_other_one,
            active=True,
        )
        cls.supporter_two.save()
        models.SupporterContact.objects.get_or_create(
            supporter=cls.supporter_two,
            account=cls.user_supporter,
        )
        cls.supporter_three = models.Supporter.objects.create(
            name='University of Essex',
            band=cls.band_other_three,
            active=True,
        )
        cls.supporter_three.save()
        models.SupporterContact.objects.get_or_create(
            supporter=cls.supporter_three,
            account=cls.user_supporter,
        )
        cls.supporter_four = models.Supporter.objects.create(
            name='University of Antwerp',
            band=cls.band_other_two,
            active=True,
        )
        cls.supporter_four.save()
        models.SupporterContact.objects.get_or_create(
            supporter=cls.supporter_four,
            account=cls.user_supporter,
        )
        cls.fake_indicator = 'ABC.DEF.GHI'
        cls.custom_page = Page.objects.create(
            content_type=ContentType.objects.get_for_model(cls.press),
            object_id=cls.press.pk,
            name='become-a-supporter',
            display_name='Become a Supporter',
        )

    @classmethod
    def tearDownClass(cls):
        cls.custom_page.delete()
        cls.supporter_four.delete()
        cls.supporter_three.delete()
        cls.supporter_two.delete()
        cls.supporter_one.delete()
        cls.band_other_two.delete()
        cls.band_other_one.delete()
        cls.band_base_country_other.delete()
        cls.band_base_level_other.delete()
        cls.band_base.delete()
        cls.currency_other.delete()
        cls.currency_base.delete()
        cls.level_third.delete()
        cls.level_other.delete()
        cls.level_base.delete()
        cls.size_other.delete()
        cls.size_base.delete()
        cls.agent_other.delete()
        cls.agent_default.delete()
        cls.user_agent.save()
        cls.user_staff.save()
        cls.user_supporter.delete()
        cls.press.delete()
        super().tearDownClass()

    def setUp(self):
        self.request = Mock(HttpRequest)
        type(self.request).GET = {}
        type(self.request).POST = {}
        type(self.request).journal = None
        type(self.request).press = Mock(press_models.Press)
        press_type = ContentType.objects.get_for_model(self.press)
        type(self.request).model_content_type = press_type
        type(self.request).site_type = self.press


class ModelTests(TestCaseWithData):

    def test_billing_agent_save(self):

        # Set up test conditions
        self.agent_other.default = True
        self.agent_other.save()
        self.agent_default.refresh_from_db()
        self.agent_other.refresh_from_db()

        # Get test values
        other_has_country = bool(self.agent_other.country)
        default_still_default = self.agent_default.default

        # Restore test data
        self.agent_default.default = True
        self.agent_default.save()
        self.agent_other.country = 'GB'
        self.agent_other.save()

        # Run test
        self.assertFalse(other_has_country)
        self.assertFalse(default_still_default)

    @patch('plugins.consortial_billing.logic.latest_multiplier_for_indicator')
    def test_currency_exchange_rate_with_typical_args(self, latest_multiplier):
        self.currency_base.exchange_rate(base_band=self.band_base_country_other)
        expected_args = (
            plugin_settings.RATE_INDICATOR,
            self.currency_base.region,  # Target currency
            self.currency_other.region, # Specified base currency
            utils.setting('missing_data_exchange_rate')
        )
        self.assertTupleEqual(
            expected_args,
            latest_multiplier.call_args.args,
        )

    @patch('plugins.consortial_billing.logic.latest_multiplier_for_indicator')
    def test_currency_exchange_rate_with_no_args(self, latest_multiplier):
        self.currency_other.exchange_rate()
        expected_args = (
            plugin_settings.RATE_INDICATOR,
            self.currency_other.region,  # Target currency
            self.currency_base.region, # Default base currency
            utils.setting('missing_data_exchange_rate')
        )
        self.assertTupleEqual(
            expected_args,
            latest_multiplier.call_args.args,
        )

    def test_band_economic_disparity(self):
        with patch(
            'plugins.consortial_billing.logic.latest_multiplier_for_indicator'
        ) as latest_multiplier:
            self.band_other_two.economic_disparity
            self.assertIn(
                plugin_settings.DISPARITY_INDICATOR,
                latest_multiplier.call_args.args,
            )
            self.assertIn(
                self.band_other_two.country.alpha3,
                latest_multiplier.call_args.args,
            )
            self.assertIn(
                self.band_base.country.alpha3,
                latest_multiplier.call_args.args,
            )

    def test_band_calculate_fee(self):
        with patch(
            'plugins.consortial_billing.logic.latest_multiplier_for_indicator',
            return_value=(decimal.Decimal(0.85), ''),
        ) as latest_multiplier:
            fee, _ = self.band_other_two.calculate_fee()
            expected_fee = round(
                5000                      # base
                # * decimal.Decimal(0.6)  # size does not matter for higher level
                * decimal.Decimal(0.85)   # Patched GNI
                * decimal.Decimal(0.85),  # Patched exchange rate
                -1
            )
            latest_multiplier.assert_called()
            self.assertEqual(fee, expected_fee)

    def test_band_determine_billing_agent(self):
        agent = self.band_base.determine_billing_agent()
        self.assertEqual(agent, self.agent_default)
        agent = self.band_other_two.determine_billing_agent()
        self.assertEqual(agent, self.agent_other)

    def test_band_save(self):
        with patch.object(
            self.band_other_two,
            'calculate_fee',
            return_value=(2000, '')
        ) as calculate_fee:
            self.band_other_two.fee = None
            self.band_other_two.save()
            calculate_fee.assert_called_once()
