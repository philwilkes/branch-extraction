import os
import sys
import glob

import numpy as np
import pandas as pd
from scipy.spatial import distance_matrix as distance_matrix
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import ply_io
import qrdar

rotation = np.array([[0, 0, 1, 0],
                     [0, -1, 0, 0],
                     [1, 0, 0, 0],
                     [0, 0, 0, 1]])

def identify_ground(pc):
    
    #voxelise and identify ground
    pc.loc[:, 'xx'] = pc.x.round()
    pc.loc[:, 'yy'] = pc.y.round()

    # rigid transform
    ground_plane = pc.groupby(['xx', 'yy']).z.min().reset_index()
    nominal_plane = ground_plane.copy()
    nominal_plane.z = 0
    M = qrdar.common.rigid_transform_3D(ground_plane.values, nominal_plane.values)
    pc.loc[:, ['x', 'y', 'z']] = qrdar.common.apply_rotation(M, pc)
    
    return pc[pc.z < .15][['x', 'y', 'z', 'reflectance']], M


def distanceFilter(corners, template):
    
    tdM = qrdar.common.expected_distances(template)
    
    # remove points that are not ~ correct distance from at least
    # 1 other according to template
    dist = distance_matrix(corners[['x', 'y', 'z']], corners[['x', 'y', 'z']])
    dist_bool = np.array([False if v == 0 
                          else True if np.any(np.isclose(v, tdM, atol=.02)) 
                          else False for v in dist.flatten()]).reshape(dist.shape)
    corners.loc[:, 'num_nbrs'] = [len(np.where(r == True)[0]) for r in dist_bool]
    remove_idx = corners[corners.num_nbrs < 1].index

    return remove_idx

if __name__ == '__main__':
    
    rp = sys.argv[1]
                
    print('processing:', rp)

    os.chdir(rp)
    n_sp = len(glob.glob('ScanPos*'))

    if not os.path.isdir('stickers'):
        os.makedirs('stickers')

    if not os.path.isdir('ply'):
        raise Exception('process rxp2ply and put in riproject folder')
    
    os.chdir('ply')

    for pcn in glob.glob('*.ply'):

        print('\tprocessing scan:', pcn)

        pc = ply_io.read_ply(pcn)
        pc = pc[pc.deviation <= 10] # specific to RIEGL
        pc.loc[:, ['x', 'y', 'z']] = qrdar.common.apply_rotation(rotation, pc) # only required if scans are tilted
        pc = pc[(pc.x.between(-2.5, 2.5)) & (pc.y.between(-3, 0)) & (pc.z.between(-1.5, 0))] # may need adjusting

        ground, ground_m = identify_ground(pc)

        bright = qrdar.search4stickers.find(ground[ground.reflectance > -1], verbose=False)
        bright = qrdar.search4stickers.filterBySize(bright, verbose=False, max_size=.05)

        stickers = bright.groupby('sticker_labels_').mean()
        idx = distanceFilter(stickers, qrdar.common.template())
        stickers = stickers.loc[~stickers.index.isin(idx)]
        if len(stickers) == 0: 
            print('\t', pcn, 'no stickers found')
            continue

        stickers.loc[:, ['x', 'y', 'z']] = qrdar.common.apply_rotation(np.linalg.inv(ground_m), stickers)
        stickers.loc[:, ['x', 'y', 'z']] = qrdar.common.apply_rotation(np.linalg.inv(rotation), stickers)

        stickers[['x', 'y', 'z']].to_csv(os.path.join('../stickers/', pcn[:-4] + '.stickers.txt'), 
                                         sep=' ', header=True)
        print('\t', pcn, len(stickers), 'found')
