import unittest
from unittest.mock import patch
from unittest.mock import Mock

from astrohack.dio import open_holog, open_image, open_panel, open_pointing, fix_pointing_table
from astrohack.gdown_utils import gdown_data, build_folder_structure

class AstroHackDioTestCase(unittest.TestCase):
    """
    #@patch('astrohack._get_astrohack_logger')
    @patch('astrohack.AstrohackHologFile')
    def test_open_holog(self, mock_holog_file, mock_logger):
        mock_logger.return_value = logger_mock = Mock()
        mock_holog_file.return_value._open.return_value = True

        file = 'path/to/holog_file.holog'
        result = open_holog(file)

        mock_holog_file.assert_called_once_with(file=file)
        mock_holog_file.return_value._open.assert_called_once()
        logger_mock.error.assert_not_called()
        self.assertEqual(result, mock_holog_file.return_value)

        mock_holog_file.return_value._open.return_value = False

        result = open_holog(file)

        logger_mock.error.assert_called_once_with(f"Error opening holography file: {file}")
        self.assertIsNone(result)

    #@patch('astrohack._get_astrohack_logger')
    @patch('astrohack.AstrohackImageFile')
    def test_open_image(self, mock_image_file, mock_logger):
        mock_logger.return_value = logger_mock = Mock()
        mock_image_file.return_value._open.return_value = True

        file = 'path/to/image_file.image'
        result = open_image(file)

        mock_image_file.assert_called_once_with(file=file)
        mock_image_file.return_value._open.assert_called_once()
        logger_mock.error.assert_not_called()
        self.assertEqual(result, mock_image_file.return_value)

        mock_image_file.return_value._open.return_value = False

        result = open_image(file)

        logger_mock.error.assert_called_once_with(f"Error opening holography image file: {file}")
        self.assertIsNone(result)

    #@patch('astrohack._get_astrohack_logger')
    @patch('astrohack.AstrohackPanelFile')
    def test_open_panel(self, mock_panel_file, mock_logger):
        mock_logger.return_value = logger_mock = Mock()
        mock_panel_file.return_value._open.return_value = True

        file = 'path/to/panel_file.panel'
        result = open_panel(file)

        mock_panel_file.assert_called_once_with(file=file)
        mock_panel_file.return_value._open.assert_called_once()
        logger_mock.error.assert_not_called()
        self.assertEqual(result, mock_panel_file.return_value)

        mock_panel_file.return_value._open.return_value = False

        result = open_panel(file)

        logger_mock.error.assert_called_once_with(f"Error opening holography panel file: {file}")
        self.assertIsNone(result)

    #@patch('astrohack._get_astrohack_logger')
    @patch('astrohack.AstrohackPointFile')
    def test_open_pointing(self, mock_point_file, mock_logger):
        mock_logger.return_value = logger_mock = Mock()
        mock_point_file.return_value._open.return_value = True

        file = 'path/to/pointing_file.pointing'
        result = open_pointing(file)

        mock_point_file.assert_called_once_with(file=file)
        mock_point_file.return_value._open.assert_called_once()
        logger_mock.error.assert_not_called()
        self.assertEqual(result, mock_point_file.return_value)

        mock_point_file.return_value._open.return_value = False

        result = open_pointing(file)

        logger_mock.error.assert_called_once_with(f"Error opening holography pointing file: {file}")
        self.assertIsNone(result)
    """
    @patch('astrohack.tables')
    def test_fix_pointing_table(self, mock_tables):

        datafolder = 'data'
        resultsfolder = 'results'
        build_folder_structure(datafolder, resultsfolder)
        gdown_data(ms_name='ea25_cal_small_after_fixed.split.ms', download_folder=datafolder)
        ms_name = './data/ea25_cal_small_after_fixed.split.ms'

        reference_antenna = ['ant1', 'ant2']

        mock_taql = Mock()
        mock_tables.taql.return_value = mock_taql

        fix_pointing_table(ms_name, reference_antenna)

        mock_tables.taql.assert_called_once_with('select NAME from {table}'.format(table='./data/ea25_cal_small_after_fixed.split.ms/ANTENNA'))
        mock_taql.getcol.assert_called_once_with('NAME')
        mock_tables.table.assert_called_once_with('./data/ea25_cal_small_after_fixed.split.ms/POINTING', readonly=False)
        mock_tables.table.return_value.getcol.assert_called_once_with('MESSAGE')
        mock_tables.table.return_value.addrows.assert_called_once_with(nrows=1)
        mock_tables.table.return_value.putcol.assert_called_once_with(columnname="MESSAGE", value='pnt_tbl:fixed', startrow=0)


if __name__ == '__main__':
    unittest.main()
