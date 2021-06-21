import pyproj
import os
import warnings
import numpy as np
from pysheds.grid import Grid
from pysheds.rfsm import RFSM

# TODO: Major todo's
# - self.mask should be a raster
# - grid.clip_to should be able to take a raster (use _input_handler)

current_dir = os.path.dirname(os.path.realpath(__file__))
data_dir = os.path.abspath(os.path.join(current_dir, '../data'))
dir_path = os.path.join(data_dir, 'dir.asc')
dem_path = os.path.join(data_dir, 'dem.tif')
roi_path = os.path.join(data_dir, 'roi.tif')
eff_path = os.path.join(data_dir, 'eff.tif')
dinf_eff_path = os.path.join(data_dir, 'dinf_eff.tif')
feature_geometry = [{'type': 'Polygon',
                      'coordinates': (((-97.29749977660477, 32.74000135435936),
                        (-97.29083107907053, 32.74000328969928),
                        (-97.29083343776601, 32.734166727851886),
                        (-97.29749995804616, 32.73416660689317),
                        (-97.29749977660477, 32.74000135435936)),)}]
out_of_bounds = [{'type': 'Polygon',
                      'coordinates': (((-97.29304075342363, 32.847513357726825),
                        (-97.28637205588939, 32.84751529306675),
                        (-97.28637441458487, 32.84167873121935),
                        (-97.29304093486502, 32.84167861026064),
                        (-97.29304075342363, 32.847513357726825)),)}]
# Initialize grid
grid = Grid()
crs = pyproj.Proj('epsg:4326', preserve_units=True)
grid.read_ascii(dir_path, 'dir', dtype=np.uint8, crs=crs)
grid.read_raster(dem_path, 'dem')
grid.read_raster(roi_path, 'roi')
grid.read_raster(eff_path, 'eff')
grid.read_raster(dinf_eff_path, 'dinf_eff')
# set nodata to 1
# why is that not working with grid.view() in test_accumulation?
#grid.eff[grid.eff==grid.eff.nodata] = 1
#grid.dinf_eff[grid.dinf_eff==grid.dinf_eff.nodata] = 1

# Initialize parameters
dirmap = (64,  128,  1,   2,    4,   8,    16,  32)
acc_in_frame = 76499
acc_in_frame_eff = 76498 # max value with efficiency
acc_in_frame_eff1 = 19125.5 # accumulation for raster cell with acc_in_frame with transport efficiency
cells_in_catch = 11422
catch_shape = (159, 169)
max_distance = 209
new_crs = pyproj.Proj('epsg:3083')
old_crs = pyproj.Proj('epsg:4326', preserve_units=True)
x, y = -97.29416666666677, 32.73749999999989


# TODO: Need to test dtypes of different constructor methods
def test_constructors():
    newgrid = grid.from_ascii(dir_path, 'dir', dtype=np.uint8, crs=crs)
    assert((newgrid.dir == grid.dir).all())
    del newgrid

def test_dtype():
    assert(grid.dir.dtype == np.uint8)

def test_nearest_cell():
    '''
    corner: snaps to nearest top/left
    center: snaps to index of cell that contains the geometry
    '''
    col, row = grid.nearest_cell(x, y, snap='corner')
    assert (col, row) == (229, 101)
    col, row = grid.nearest_cell(x, y, snap='center')
    assert (col, row) == (228, 100)

def test_catchment():
    # Reference routing
    grid.catchment(x, y, data='dir', dirmap=dirmap, out_name='catch',
                recursionlimit=15000, xytype='label')
    assert(np.count_nonzero(grid.catch) == cells_in_catch)
    col, row = grid.nearest_cell(x, y)
    catch_ix = grid.catchment(col, row, data='dir', dirmap=dirmap, inplace=False,
                              recursionlimit=15000, xytype='index')

def test_clip():
    grid.clip_to('catch')
    assert(grid.shape == catch_shape)
    assert(grid.view('catch').shape == catch_shape)

def test_fill_depressions():
    depressions = grid.detect_depressions('dem')
    filled = grid.fill_depressions('dem', inplace=False)

def test_resolve_flats():
    flats = grid.detect_flats('dem')
    assert(flats.sum() > 100)
    grid.resolve_flats(data='dem', out_name='inflated_dem')
    flats = grid.detect_flats('inflated_dem')
    # TODO: Ideally, should show 0 flats
    assert(flats.sum() <= 32)

def test_flowdir():
    grid.clip_to('dir')
    grid.flowdir(data='inflated_dem', dirmap=dirmap, routing='d8', out_name='d8_dir')
    grid.flowdir(data='inflated_dem', dirmap=dirmap, routing='d8', as_crs=new_crs,
                 out_name='proj_dir')

def test_dinf_flowdir():
    grid.flowdir(data='inflated_dem', dirmap=dirmap, routing='dinf', out_name='dinf_dir')
    dinf_fdir = grid.flowdir(data='inflated_dem', dirmap=dirmap, routing='dinf', as_crs=new_crs,
                             inplace=False)

def test_raster_input():
    fdir = grid.flowdir(grid.inflated_dem, inplace=False)

def test_clip_pad():
    grid.clip_to('catch')
    no_pad = grid.view('catch')
    for p in (1, 4, 10):
        grid.clip_to('catch', pad=(p,p,p,p))
        assert((no_pad == grid.view('catch')[p:-p, p:-p]).all())
    # TODO: Should check for non-square padding

def test_computed_fdir_catch():
    grid.catchment(x, y, data='d8_dir', dirmap=dirmap, out_name='d8_catch',
                   routing='d8', recursionlimit=15000, xytype='label')
    assert(np.count_nonzero(grid.catch) > 11300)
    # Reference routing
    grid.catchment(x, y, data='dinf_dir', dirmap=dirmap, out_name='dinf_catch',
                   routing='dinf', recursionlimit=15000, xytype='label')
    assert(np.count_nonzero(grid.catch) > 11300)

def test_accumulation():
    # TODO: This breaks if clip_to's padding of dir is nonzero
    grid.clip_to('dir')
    grid.accumulation(data='dir', dirmap=dirmap, out_name='acc')
    assert(grid.acc.max() == acc_in_frame)
    # set nodata to 1
    eff = grid.view("eff")
    eff[eff==grid.eff.nodata] = 1
    grid.accumulation(data='dir', dirmap=dirmap, out_name='acc_eff', efficiency=eff)
    assert(abs(grid.acc_eff.max() - acc_in_frame_eff) < 0.001)
    assert(abs(grid.acc_eff[grid.acc==grid.acc.max()] - acc_in_frame_eff1) < 0.001)
    # TODO: Should eventually assert: grid.acc.dtype == np.min_scalar_type(grid.acc.max())
    grid.clip_to('catch', pad=(1,1,1,1))
    grid.accumulation(data='catch', dirmap=dirmap, out_name='acc')
    assert(grid.acc.max() == cells_in_catch)
    # Test accumulation on computed flowdirs
    grid.accumulation(data='d8_dir', dirmap=dirmap, out_name='d8_acc', routing='d8')
    grid.accumulation(data='dinf_dir', dirmap=dirmap, out_name='dinf_acc', routing='dinf')
    grid.accumulation(data='dinf_dir', dirmap=dirmap, out_name='dinf_acc', as_crs=new_crs,
                      routing='dinf')
    assert(grid.d8_acc.max() > 11300)
    assert(grid.dinf_acc.max() > 11400)
    #set nodata to 1
    eff = grid.view("dinf_eff")
    eff[eff==grid.dinf_eff.nodata] = 1
    grid.accumulation(data='dinf_dir', dirmap=dirmap, out_name='dinf_acc_eff', routing='dinf',
                      efficiency=eff)
    pos = np.where(grid.dinf_acc==grid.dinf_acc.max())
    assert(np.round(grid.dinf_acc[pos] / grid.dinf_acc_eff[pos]) == 4.)

def test_hand():
    grid.compute_hand('dir', 'dem', grid.acc > 100)

def test_flow_distance():
    grid.clip_to('catch')
    grid.flow_distance(x, y, data='catch', dirmap=dirmap, out_name='dist', xytype='label')
    assert(grid.dist[~np.isnan(grid.dist)].max() == max_distance)
    col, row = grid.nearest_cell(x, y)
    grid.flow_distance(col, row, data='catch', dirmap=dirmap, out_name='dist', xytype='index')
    assert(grid.dist[~np.isnan(grid.dist)].max() == max_distance)
    grid.flow_distance(x, y, data='dinf_dir', dirmap=dirmap, routing='dinf',
                       out_name='dinf_dist', xytype='label')
    grid.flow_distance(x, y, data='catch', weights=np.ones(grid.size),
                       dirmap=dirmap, out_name='dist', xytype='label')
    grid.flow_distance(x, y, data='dinf_dir', dirmap=dirmap, weights=np.ones((grid.size, 2)),
                       routing='dinf', out_name='dinf_dist', xytype='label')

def test_set_nodata():
    grid.set_nodata('dir', 0)

def test_to_ascii():
    grid.clip_to('catch')
    grid.to_ascii('dir', 'test_dir.asc', view=False, apply_mask=False, dtype=np.float)
    grid.read_ascii('test_dir.asc', 'dir_output', dtype=np.uint8)
    assert((grid.dir_output == grid.dir).all())
    grid.to_ascii('dir', 'test_dir.asc', view=True, apply_mask=True, dtype=np.uint8)
    grid.read_ascii('test_dir.asc', 'dir_output', dtype=np.uint8)
    assert((grid.dir_output == grid.view('catch')).all())

def test_to_raster():
    grid.clip_to('catch')
    grid.to_raster('dir', 'test_dir.tif', view=False, apply_mask=False, blockxsize=16, blockysize=16)
    grid.read_raster('test_dir.tif', 'dir_output')
    assert((grid.dir_output == grid.dir).all())
    assert((grid.view('dir_output') == grid.view('dir')).all())
    grid.to_raster('dir', 'test_dir.tif', view=True, apply_mask=True, blockxsize=16, blockysize=16)
    grid.read_raster('test_dir.tif', 'dir_output')
    assert((grid.dir_output == grid.view('catch')).all())
    # TODO: Write test for windowed reading

def test_from_raster():
    grid.clip_to('catch')
    grid.to_raster('dir', 'test_dir.tif', view=False, apply_mask=False, blockxsize=16, blockysize=16)
    newgrid = Grid.from_raster('test_dir.tif', 'dir_output')
    newgrid.clip_to('dir_output')
    assert ((newgrid.dir_output == grid.dir).all())
    grid.to_raster('dir', 'test_dir.tif', view=True, apply_mask=True, blockxsize=16, blockysize=16)
    newgrid = Grid.from_raster('test_dir.tif', 'dir_output')
    assert((newgrid.dir_output == grid.view('catch')).all())

def test_windowed_reading():
    newgrid = Grid.from_raster('test_dir.tif', 'dir_output', window=grid.bbox, window_crs=grid.crs)

def test_mask_geometry():
    grid = Grid.from_raster(dem_path,'dem', mask_geometry=feature_geometry)
    rows = np.array([225, 226, 227, 228, 229, 230, 231, 232] * 7)
    cols = np.array([np.arange(98,105)] * 8).T.reshape(1,56)
    masked_cols, masked_rows = grid.mask.nonzero()
    assert (masked_cols == cols).all()
    assert (masked_rows == rows).all()
    with warnings.catch_warnings(record=True) as warn:
        warnings.simplefilter("always")
        grid = Grid.from_raster(dem_path,'dem', mask_geometry=out_of_bounds)
        assert len(warn) == 1
        assert issubclass(warn[-1].category, UserWarning)
        assert "does not fall within the bounds" in str(warn[-1].message)
        assert grid.mask.all(), "mask should be returned to all True as normal"

def test_properties():
    bbox = grid.bbox
    assert(len(bbox) == 4)
    assert(isinstance(bbox, tuple))
    extent = grid.extent
    assert(len(extent) == 4)
    assert(isinstance(extent, tuple))

def test_extract_river_network():
    rivers = grid.extract_river_network('catch', grid.view('acc', nodata=0) > 20)
    assert(isinstance(rivers, dict))
    # TODO: Need more checks here. Check if endnodes equals next startnode

def test_view_methods():
    grid.view('dem', interpolation='spline')
    grid.view('dem', interpolation='linear')
    grid.view('dem', interpolation='cubic')
    grid.view('dem', interpolation='linear', as_crs=new_crs)
    # TODO: Need checks for these
    grid.view(grid.dem)

def test_resize():
    new_shape = tuple(np.asarray(grid.shape) // 2)
    grid.resize('dem', new_shape=new_shape)

def test_pits():
    # TODO: Need dem with pits
    pits = grid.detect_pits('dem')
    assert(~pits.any())
    filled = grid.fill_pits('dem', inplace=False)

def test_other_methods():
    grid.cell_area(out_name='area', as_crs=new_crs)
    # TODO: Not a super robust test
    assert((grid.area.mean() > 7000) and (grid.area.mean() < 7500))
    # TODO: Need checks for these
    grid.cell_distances('dir', as_crs=new_crs, dirmap=dirmap)
    grid.cell_dh(fdir='dir', dem='dem', dirmap=dirmap)
    grid.cell_slopes(fdir='dir', dem='dem', as_crs=new_crs, dirmap=dirmap)

def test_snap_to():
    # TODO: Need checks
    grid.snap_to_mask(grid.view('acc') > 1000, [[-97.3, 32.72]])

def test_set_bbox():
    new_xmin = (grid.bbox[2] + grid.bbox[0]) / 2
    new_ymin = (grid.bbox[3] + grid.bbox[1]) / 2
    new_xmax = grid.bbox[2]
    new_ymax = grid.bbox[3]
    new_bbox = (new_xmin, new_ymin, new_xmax, new_ymax)
    grid.set_bbox(new_bbox)
    grid.clip_to('catch')
    # TODO: Need to check that everything was reset properly

def test_set_indices():
    new_xmin = int(grid.shape[1] // 2)
    new_ymin = int(grid.shape[0])
    new_xmax = int(grid.shape[1])
    new_ymax = int(grid.shape[0] // 2)
    new_indices = (new_xmin, new_ymin, new_xmax, new_ymax)
    grid.set_indices(new_indices)
    grid.clip_to('catch')
    # TODO: Need to check that everything was reset properly

def test_polygonize_rasterize():
    shapes = grid.polygonize()
    raster = grid.rasterize(shapes)
    assert (raster == grid.mask).all()

def test_detect_cycles():
    cycles = grid.detect_cycles('dir')

def test_add_gridded_data():
    grid.add_gridded_data(grid.dem, data_name='dem_copy')

def test_rfsm():
    grid.clip_to('roi')
    dem = grid.view('roi')
    rfsm = RFSM(dem)
    rfsm.reset_volumes()
    area = np.abs(grid.affine.a * grid.affine.e)
    input_vol = 0.1*area*np.ones(dem.shape)
    waterlevel = rfsm.compute_waterlevel(input_vol)
    end_vol = (area*np.where(waterlevel, waterlevel - dem, 0)).sum()
    assert np.allclose(end_vol, input_vol.sum())
