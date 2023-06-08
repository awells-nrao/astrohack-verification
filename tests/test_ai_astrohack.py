import unittest
from unittest.mock import patch

from astrohack.dio import open_holog, open_image, open_panel, open_pointing, fix_pointing_table


class MyModuleTestCase(unittest.TestCase):
    @patch('my_module._get_astrohack_logger')
    @patch('my_module.AstrohackHologFile')
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

    @patch('my_module._get_astrohack_logger')
    @patch('my_module.AstrohackImageFile')
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

    @patch('my_module._get_astrohack_logger')
    @patch('my_module.AstrohackPanelFile')
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

    @patch('my_module._get_astrohack_logger')
    @patch('my_module.AstrohackPointFile')
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

    @patch('my_module.tables')
    def test_fix_pointing_table(self, mock_tables
