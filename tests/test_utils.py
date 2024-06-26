__copyright__ = "Copyright 2023 Birkbeck, University of London"
__author__ = "Open Library of Humanities"
__license__ = "AGPL v3"
__maintainer__ = "Open Library of Humanities"

from unittest.mock import patch, Mock, PropertyMock
import decimal

from plugins.consortial_billing import utils, models as supporter_models
from plugins.consortial_billing.tests import test_models

CB = 'plugins.consortial_billing'


class UtilsTests(test_models.TestCaseWithData):

    def test_form_world_bank_url(self):
        url = utils.form_world_bank_url(self.fake_indicator, '2023')
        self.assertEqual(
            url,
            'https://api.worldbank.org/v2/country/all/indicator/'
            f'{self.fake_indicator}?date=2023&format=json&per_page=500',
        )

    def test_save_and_open_use_same_label(self):
        with patch(
            'plugins.consortial_billing.utils.save_media_file'
        ) as save_label:
            with patch('cms.models.MediaFile.objects.get') as get_label:
                with patch(f'{CB}.utils.load_json_with_decimals'):
                    utils.save_file_for_indicator_and_year(
                        self.fake_indicator,
                        2023,
                        '',
                    )
                    utils.open_saved_world_bank_data(
                        self.fake_indicator,
                        2023,
                    )
                    saved_as = save_label.call_args.args[0]
                    opened_as = get_label.call_args.kwargs['label']
                    self.assertEqual(saved_as, opened_as)

    def test_fetch_world_bank_data_200(self):
        with patch(
            'plugins.consortial_billing.utils.save_file_for_indicator_and_year'
        ) as save_file:
            with patch('requests.get') as mock_get:
                response = Mock()
                type(response).status_code = PropertyMock(return_value=200)
                mock_get.return_value = response
                status_code = utils.fetch_world_bank_data(
                    self.fake_indicator,
                    2023,
                )
                save_file.assert_called()
                self.assertEqual(status_code, 200)

    def test_fetch_world_bank_data_404(self):
        with patch(
            'plugins.consortial_billing.utils.save_file_for_indicator_and_year'
        ) as save_file:
            with patch('requests.get') as mock_get:
                response = Mock()
                type(response).status_code = PropertyMock(return_value=404)
                mock_get.return_value = response
                status_code = utils.fetch_world_bank_data(
                    self.fake_indicator,
                    2023,
                )
                save_file.assert_not_called()
                self.assertEqual(status_code, 404)

    def test_make_table_showing_all_levels_by_country_and_size(self):
        with patch(
            'plugins.consortial_billing.logic.latest_multiplier_for_indicator',
            return_value=(decimal.Decimal(0.85), ''),
        ):
            data = utils.make_table_showing_all_levels_by_country_and_size()
            self.assertEqual(
                data['thead'][0],
                'Standard'
            )
            small = data['tbody']['Small (0-4,999 students)']
            self.assertEqual(
                small['UK']['Silver']['currency'],
                '£'
            )
            large = data['tbody']['Large (10,000+ students)']
            self.assertGreater(
                large['US']['Standard']['fee'],
                decimal.Decimal(0)
            )

    @patch(f'{CB}.logic.latest_multiplier_for_indicator')
    def test_make_table_of_higher_supporters_by_country_and_level(self, mult):
        mult.return_value = (0.85, '')
        data = utils.make_table_of_higher_supporters_by_country_and_level()
        self.assertEqual(
            data['thead'][0],
            'Silver'
        )
        self.assertEqual(
            data['tbody']['UK']['Silver']['currency'],
            '£'
        )

    @patch(f'{CB}.logic.latest_multiplier_for_indicator')
    def test_make_table_of_standard_supporters_by_country_and_size(self, mult):
        mult.return_value = (decimal.Decimal(0.85), '')
        data = utils.make_table_of_standard_supporters_by_country_and_size()
        self.assertEqual(
            data['thead'][0],
            'Small (0-4,999 students)'
        )
        self.assertEqual(
            data['tbody']['UK']['Small (0-4,999 students)']['currency'],
            '£'
        )

    @patch(f'{CB}.utils.save_media_file')
    @patch(f'{CB}.utils.generate_new_demo_data')
    def test_update_demo_band_data(self, generate_new, save_media_file):
        generate_new.return_value = []
        utils.update_demo_band_data()
        generate_new.assert_called()
        save_media_file.assert_called()

    @patch(f'{CB}.utils.load_json_with_decimals')
    @patch('cms.models.MediaFile.objects.get')
    def test_get_saved_demo_band_data(self, media_get, load_json):
        utils.get_saved_demo_band_data()
        media_get.assert_called()
        load_json.assert_called()

    @patch('builtins.open')
    @patch('json.loads')
    def test_load_json_with_decimals(self, json_loads, patched_open):
        with patched_open('fake/path/to/file', 'r') as file_ref:
            utils.load_json_with_decimals(file_ref)
            self.assertIn(
                ('parse_float', decimal.Decimal),
                json_loads.call_args.kwargs.items(),
            )
            self.assertIn(
                ('parse_int', decimal.Decimal),
                json_loads.call_args.kwargs.items(),
            )

    def test_get_standard_support_level(self):
        level = utils.get_standard_support_level()
        self.assertEqual(level, self.level_standard)

    def test_get_standard_support_level_no_default(self):

        # Make it so there is no default
        self.level_standard.default = False
        self.level_standard.save()

        level = utils.get_standard_support_level()
        self.assertEqual(level, self.level_standard)

        # Restore data
        self.level_standard.default = True
        self.level_standard.save()

    @patch('requests.get')
    @patch('json.loads')
    def test_get_ror(self, json_loads, mock_get):
        json_loads.return_value = {
            'items': [
                {
                    'chosen': True,
                    'matching_type': 'EXACT',
                    'organization': {
                        'id': 'The Holy Grorl'
                    }
                }
            ]
        }
        response = Mock()
        type(response).status_code = PropertyMock(return_value=200)
        mock_get.return_value = response
        name = 'Organization Name'
        ror = utils.get_ror(name)
        mock_get.assert_called_once_with(
            f'https://api.ror.org/organizations?affiliation=Organization+Name'
        )
        self.assertEqual(ror, 'The Holy Grorl')
