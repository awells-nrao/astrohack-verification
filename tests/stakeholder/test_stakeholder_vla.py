import pytest

import shutil
import os
import json
import copy
import astrohack

import numpy as np

from astrohack.gdown_utils import gdown_data

from astrohack._utils._tools import _jsonify

from astrohack.extract_holog import extract_holog
from astrohack.holog import holog
from astrohack.panel import panel

from astrohack.dio import open_panel

from astrohack.astrohack_client import astrohack_local_client

base_name = 'ea25_cal_small_'

client = astrohack_local_client(cores=2, memory_limit='8GB', log_parms={'log_level':'DEBUG'})

@pytest.fixture(scope='session')
def set_data(tmp_path_factory):
  data_dir = tmp_path_factory.mktemp("data")
    
  # Data files
  astrohack.gdown_utils.download('ea25_cal_small_before_fixed.split.ms', folder=str(data_dir), unpack=True)
  astrohack.gdown_utils.download('ea25_cal_small_after_fixed.split.ms', folder=str(data_dir), unpack=True)

  # Verification json information
  astrohack.gdown_utils.download(file='extract_holog_verification.json', folder=str(data_dir))
  astrohack.gdown_utils.download(file='holog_numerical_verification.json', folder=str(data_dir))

  # Download holog mds files
  #astrohack.gdown_utils.download(file='alma-test', folder=str(data_dir), unpack=True)
  #astrohack.gdown_utils.download(file='vla-test', folder=str(data_dir), unpack=True)

  return data_dir

def relative_difference(result, expected):  
      return 2*np.abs(result - expected)/(abs(result) + abs(expected))
'''
def verify_panel_positions(
    data_dir="",
    panel_list=['3-11', '5-31', '7-52', '11-62'], 
    reference_position = np.array([-2.39678052, -0.87024129, 0.89391852, 0.48643069]),
    antenna='ant_DV13',
    ddi='ddi_0'
):
    
  M_TO_MILS = 39370.1
    
  panel_mds = open_panel('{data}/alma.split.panel.zarr'.format(data=data_dir))
    
  panel_position = np.mean(panel_mds[antenna][ddi].sel(labels=panel_list).PANEL_SCREWS.values*M_TO_MILS, axis=1)

  relative_position = relative_difference(panel_position, reference_position)
    
  return np.any(relative_position < 1e-6)
  '''

def verify_panel_shifts(
  data_dir="",
  panel_list=['3-4', '5-27', '5-37', '5-38'], 
  expected_shift=np.array([-100, 75, 0, 150]),
  ref_mean_shift = np.array([-112.23760235, 73.09423151, -1.52957784, 138.96735818]),
  antenna='ant_ea25',
  ddi='ddi_0'
):
    def relative_difference(mean, expected):  
      return 2*np.abs(mean - expected)/(abs(mean) + abs(expected))
    
    M_TO_MILS = 39370.1
    
    before_mds = open_panel('{data}/vla.before.split.panel.zarr'.format(data=data_dir))
    after_mds = open_panel('{data}/vla.after.split.panel.zarr'.format(data=data_dir))
    
    before_shift = before_mds[antenna][ddi].sel(labels=panel_list).PANEL_SCREWS.values*M_TO_MILS
    after_shift = after_mds[antenna][ddi].sel(labels=panel_list).PANEL_SCREWS.values*M_TO_MILS
    
    difference = after_shift - before_shift
    
    mean_shift = np.mean(difference, axis=1)

    delta_mean_shift = np.abs(mean_shift - expected_shift)
    delta_ref_shift = np.abs(ref_mean_shift - expected_shift)
        
    delta_shift = delta_mean_shift - delta_ref_shift   # New corrections - old corrections --> delta if delta < 0 ==> we improved.
    relative_shift = relative_difference(delta_mean_shift, delta_ref_shift)
    
    return np.all(relative_shift < 1e-6)

def verify_center_pixels(file, antenna, ddi, reference_center_pixels, number_of_digits=7):
    from astrohack.dio import open_image
    
    mds = open_image(file)[antenna][ddi]
    
    aperture_shape = mds.APERTURE.values.shape[-2], mds.APERTURE.values.shape[-1]
    beam_shape = mds.BEAM.values.shape[-2], mds.BEAM.values.shape[-1]    
    
    aperture_center_pixels = np.squeeze(mds.APERTURE.values[..., aperture_shape[0]//2, aperture_shape[1]//2])
    beam_center_pixels = np.squeeze(mds.BEAM.values[..., beam_shape[0]//2, beam_shape[1]//2])
    
    aperture_ref = list(map(complex, reference_center_pixels['aperture']))
    beam_ref = list(map(complex, reference_center_pixels['beam']))
    
    for i in range(len(aperture_ref)):
        # Should probably write a custom round function here
        aperture_check = round(aperture_ref[i].real, number_of_digits) == round(aperture_center_pixels[i].real, number_of_digits)
        beam_check = round(beam_ref[i].real, number_of_digits) == round(beam_center_pixels[i].real, number_of_digits)
    
        real_check = aperture_check and beam_check

        aperture_check = round(aperture_ref[i].imag, number_of_digits) == round(aperture_center_pixels[i].imag, number_of_digits)
        beam_check = round(beam_ref[i].imag, number_of_digits) == round(beam_center_pixels[i].imag, number_of_digits)

        imag_check = aperture_check and beam_check

    return real_check and imag_check   
                
def verify_holog_obs_dictionary(holog_obs_dict):

    ref_holog_obj = {}
    ref_holog_obj = copy.deepcopy(holog_obs_dict)

    _jsonify(ref_holog_obj)

    with open(".holog_obs_dict.json") as json_file:
        holog_obj = json.load(json_file)
                          
    return  holog_obj == ref_holog_obj

def verify_holog_diagnostics(json_data, truth_json, tolerance=1e-7):
    
    with open(truth_json) as file:
        reference_dict = json.load(file)
        
    cell_size = reference_dict["vla"]['cell_size'][1]
    grid_size = float(reference_dict["vla"]['grid_size'][1])
    
    json_data['cell_size'] = np.abs(float(json_data['cell_size']))
    
    cell_size = np.abs(float(cell_size))

    return (relative_difference(json_data['cell_size'], cell_size) < tolerance) and (relative_difference(np.sqrt(int(json_data['n_pix'])), grid_size) < tolerance)

def test_holography_pipeline(set_data):
    before_ms = str(set_data/"".join((base_name,"before_fixed.split.ms")))
    before_holog = str(set_data/"vla.before.split.holog.zarr")
    after_ms =  str(set_data/"".join((base_name, "after_fixed.split.ms")))
    after_holog = str(set_data/"vla.after.split.holog.zarr")

    with open(str(set_data/"extract_holog_verification.json")) as file:
      holog_obs_dict = json_dict = json.load(file)

    extract_holog(
      ms_name=before_ms, 
      holog_name=before_holog, 
      ddi=[0],
      data_column='CORRECTED_DATA',
      parallel=False,
      overwrite=True,
      reuse_point_zarr=False
    )

    assert verify_holog_obs_dictionary(holog_obs_dict["vla"]["before"])


    holog_mds_after, _ = extract_holog(
        ms_name=after_ms, 
        holog_name=after_holog,
        data_column='CORRECTED_DATA',
        parallel=False,
        overwrite=True,
        reuse_point_zarr=False
    )

    with open(str(set_data/"vla.before.split.holog.zarr/.holog_attr")) as attr_file:
      holog_attr = json.load(attr_file)
    
    assert verify_holog_diagnostics(
      json_data=holog_attr,
      truth_json=str(set_data/"holog_numerical_verification.json"),
      tolerance=1e-4
    )


    assert verify_holog_obs_dictionary(holog_obs_dict["vla"]["after"])

    
    with open(str(set_data/"holog_numerical_verification.json")) as file:
      reference_dict = json.load(file)


    before_holog = str(set_data/"vla.before.split.holog.zarr")
    after_holog = str(set_data/"vla.after.split.holog.zarr")

    before_image = str(set_data/"vla.before.split.image.zarr")
    after_image = str(set_data/"vla.after.split.image.zarr")
  
    holog(
      holog_name=before_holog, 
      padding_factor=50, 
      grid_interpolation_mode='linear',
      chan_average = True,
      scan_average = True,
      overwrite=True,
      phase_fit=True,
      apply_mask=True,
      to_stokes=True,
      parallel=True
    )
  
    assert verify_center_pixels(
      file=before_image, 
      antenna='ant_ea25',
      ddi='ddi_0',
      reference_center_pixels=reference_dict["vla"]["pixels"]["before"]
    )

    holog(
      holog_name=after_holog, 
      padding_factor=50, 
      grid_interpolation_mode='linear',
      chan_average = True,
      scan_average = True,
      overwrite=True,
      phase_fit=True,
      apply_mask=True,
      to_stokes=True,
      parallel=True
    )

    assert verify_center_pixels(
      file=after_image, 
      antenna='ant_ea25',
      ddi='ddi_0',
      reference_center_pixels=reference_dict["vla"]["pixels"]["after"]
    )

    
    before_image = str(set_data/"vla.before.split.image.zarr")
    after_image = str(set_data/"vla.after.split.image.zarr")

    before_panel = panel(
      image_name=before_image, 
      panel_model='rigid',
      parallel=True,
      overwrite=True
    )

    after_panel = panel(
      image_name=after_image, 
      panel_model='rigid',
      parallel=True,
      overwrite=True
    )

    assert verify_panel_shifts(data_dir=str(set_data))