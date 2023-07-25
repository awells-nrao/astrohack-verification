import unittest
from unittest.mock import patch
from astrohack.astrohack_client import astrohack_local_client
"""
In this unit test, we use the unittest module to define a test case class TestAstrohackLocalClient.
The astrohack_local_client function is imported from the module my_module. 
We use the @patch decorator from the unittest.mock module 
to mock the dask.distributed.LocalCluster and dask.distributed.Client classes.

The test_astrohack_local_client method tests the behavior of the astrohack_local_client function
by passing in sample arguments and verifying that the expected calls to LocalCluster 
and Client are made with the correct parameters. 
Finally, we assert that the return value of the function matches the expected result.

To run the unit test, you can save the code in a file (e.g., test_astrohack_local_client.py)
and execute it using any test runner or by
running python -m unittest test_astrohack_local_client.py in the command line.
"""
class TestAstrohackLocalClient(unittest.TestCase):

    @patch('dask.distributed.LocalCluster')
    @patch('dask.distributed.Client')
    def test_astrohack_local_client(self, mock_client, mock_cluster):
        cores = 4
        memory_limit = '8GB'
        dask_local_dir = './dask-worker-space'
        log_parms = {
            'log_to_term': True,
            'log_level': 'INFO',
            'log_to_file': False,
            'log_file': None
        }
        worker_log_parms = {
            'log_to_term': False,
            'log_level': 'INFO',
            'log_to_file': False,
            'log_file': None
        }

        # Call the function
        result = astrohack_local_client(cores=cores, memory_limit=memory_limit, dask_local_dir=dask_local_dir,
                                        log_parms=log_parms, worker_log_parms=worker_log_parms)

        # Assertions
        self.assertTrue(mock_client.called)
        self.assertTrue(mock_cluster.called)
        mock_cluster.assert_called_with(n_workers=cores, threads_per_worker=1, processes=True,
                                        memory_limit=memory_limit, silence_logs=unittest.mock.ANY)
        mock_client.assert_called_with(mock_cluster.return_value)
        self.assertEqual(result, mock_client.return_value)

if __name__ == '__main__':
    unittest.main()
