import os
import glob
import multiprocessing
import itertools
import argparse

import numpy as np
import pandas as pd
import matplotlib.image as mpimg
from sklearn.cluster import DBSCAN
from subprocess import PIPE, Popen
import scipy.spatial
from scipy.optimize import curve_fit
import warnings
warnings.simplefilter(action='ignore', category=Warning)

import qrdar
import pcd_io
import ply_io

# def apply_rotation(M, df):
    
#     if 'a' not in df.columns:
#         df.loc[:, 'a'] = 1
    
#     r_ = np.dot(M, df[['x', 'y', 'z', 'a']].T).T
#     df.loc[:, ['x', 'y', 'z']] = r_[:, :3]
    
#     return df[['x', 'y', 'z']]

# def apply_rotation_2D(M, df):
    
#     if 'a' not in df.columns:
#         df.loc[:, 'a'] = 1
    
#     r_ = np.dot(M, df[['x', 'y', 'a']].T).T
#     df.loc[:, ['x', 'y']] = r_[:, :2]
    
#     return df[['x', 'y']]

def rigid_transform_3D(A, B, d=3):
    
    """
    http://nghiaho.com/uploads/code/rigid_transform_3D.py_
    """
    
    assert len(A) == len(B)
    
    A = np.matrixlib.defmatrix.matrix(A)
    B = np.matrixlib.defmatrix.matrix(B)

    N = A.shape[0]; # total points

    centroid_A = mean(A, axis=0).reshape(1, d)
    centroid_B = mean(B, axis=0).reshape(1, d)
    
    # centre the points
    AA = A - np.tile(centroid_A, (N, 1))
    BB = B - np.tile(centroid_B, (N, 1))

    # dot is matrix multiplication for array
    H = transpose(AA) * BB

    U, S, Vt = linalg.svd(H)

    R = np.dot(Vt.T, U.T)
    
    t = -R*centroid_A.T + centroid_B.T
    
    M, N = np.identity(d+1), np.identity(d+1)
    M[:d, :d] = R
    N[:d, d] = t.reshape(-1, d)
    
    return np.dot(N, M)

def read_aruco2(pc, 
                expected, 
                figs=False, 
                marker_template=None, 
                codes_dict='aruco_mip_16h3',
                verbose=False):
    
    if verbose: print ("extracting aruco")
    
    pc.loc[:, 'intensity'] = pc.refl
    targets = qrdar.identify_codes(pc, 
                                   expected=expected, 
                                   print_figure=True,
                                   marker_template=marker_template,
                                   codes_dict=codes_dict)
    targets.rename(columns={'code':'aruco'}, inplace=True)
    targets = targets[targets.confidence == 1]
    targets.reset_index(inplace=True)
    
    return targets#[['aruco', 'x', 'y']]

def identify_ground2(pc, target_centres):
    
    nominal_plane = target_centres[['x', 'y', 'z']].copy()
    nominal_plane.z = 0
    M = qrdar.common.rigid_transform_3D(target_centres[['x', 'y', 'z']].astype(float).values, 
                                        nominal_plane.astype(float).values)
    pc.loc[:, ['x', 'y', 'z']] = qrdar.common.apply_rotation(M, pc)
    pc.loc[pc.z < .05, 'is_branch'] = False
    
    return pc, M

def find_buckets(pc, target_centres, N, bucket_height=.38, bucket_radius=.15):
    
    """
    Returns: pc, bucket_centres
    """
    
    ### find buckets and remove ###
    print ('finding buckets')
    buckets = pc[pc.z.between(.1, .3)]

    # voxelise to speed-up dbscan
    buckets.loc[:, 'xx'] = (buckets.x // .005) * .005
    buckets.loc[:, 'yy'] = (buckets.y // .005) * .005
    buckets.loc[:, 'zz'] = (buckets.z // .005) * .005
    buckets.sort_values(['xx', 'yy', 'zz', 'refl'], inplace=True)
    bucket_voxels = buckets[~buckets[['xx', 'yy', 'zz']].duplicated()]

    dbscan = DBSCAN(min_samples=20, eps=.05).fit(bucket_voxels[['xx', 'yy', 'zz']])
    bucket_voxels.loc[:, 'labels_'] = dbscan.labels_
    # merge results back
    buckets = pd.merge(buckets, bucket_voxels[['xx', 'yy', 'zz', 'labels_']], on=['xx', 'yy', 'zz'])

    # find three largest targets (assumed buckets)
    labels = buckets.labels_.value_counts().index[:N]
    buckets = buckets[buckets.labels_.isin(labels)]
    bucket_centres = buckets.groupby('labels_')[['x', 'y']].mean().reset_index()
    bucket_centres.loc[:, 'aruco'] = -1

    try:
        # pair up aruco and buckets , identify and label bucket points
        for i, lbl in enumerate(buckets.labels_.unique()):
            bucket = buckets[buckets.labels_ == lbl]
            X, Y = bucket[['x', 'y']].mean(), target_centres[['x', 'y']].astype(float)
            dist2bucket = np.linalg.norm(X - Y, axis=1)
            aruco = target_centres.loc[np.where(dist2bucket == dist2bucket.min())].aruco.values[0]
            print ('bucket {} associated with aruco {}'.format(lbl, aruco))
            bucket_centres.loc[bucket_centres.labels_ == lbl, 'aruco'] = aruco

            # identify buckets points
            x_shift = bucket_centres[bucket_centres.aruco == aruco].x.values
            y_shift = bucket_centres[bucket_centres.aruco == aruco].y.values
            pc.dist = np.sqrt((pc.x - x_shift)**2 + (pc.y - y_shift)**2)
            idx = pc[(pc.z < bucket_height) & (pc.dist < bucket_radius) & (pc.is_branch)].index
            pc.loc[idx, 'is_branch'] = False

            # label branch base with aruco
            idx = pc[(pc.z < bucket_height + .5) & (pc.dist < bucket_radius)].index
            pc.loc[idx, 'aruco'] = aruco
            
    except Exception as err:
        plt.scatter(buckets.x.loc[::100], buckets.y.loc[::100], c=buckets.labels_.loc[::100])
        plt.scatter(target_centres.x, target_centres.y)
        [plt.text(r.x, r.y, r.aruco) for ix, r in target_centres.iterrows()]
        raise Exception
        
    return pc, bucket_centres

def isolate_branches(pc, N, translation, odir):
    
    print ('\tsegmenting branches')
    min_sample, iterate = 10, True
    
    while iterate:
        branches = pc[pc.is_branch]
        branches.loc[:, 'xx'] = (branches.x // .005) * .005
        branches.loc[:, 'yy'] = (branches.y // .005) * .005
        branches.loc[:, 'zz'] = (branches.z // .005) * .005
        branch_voxels = branches[~branches[['xx', 'yy', 'zz']].duplicated()]
        
        dbscan = DBSCAN(min_samples=min_sample, eps=.02).fit(branch_voxels[['xx', 'yy', 'zz']])
        branch_voxels.loc[:, 'labels_'] = dbscan.labels_
        branches = pd.merge(branches, branch_voxels[['xx', 'yy', 'zz', 'labels_']], on=['xx', 'yy', 'zz'])
        labels = branches.labels_.value_counts().index[:N]
        branches = branches[branches.labels_.isin(labels)]
        width = branches.groupby('labels_').agg({'x':np.ptp, 'y':np.ptp})
        if np.any(width < .1):
            min_sample += 10
        else: iterate = False
            
    cols = [u'pid', u'tot_rtn', u'x', u'y', u'z', u'dev', u'refl', u'rtn_N', u'sel', u'sp', u'rng', u'spot_size']
    
    for i, label in enumerate(branches.labels_.unique()):
        b = branches[branches.labels_ == label]
        aruco = b[(b.z < .5) & (~np.isnan(b.aruco))].aruco.value_counts().index[0]
        tag = translation[(translation.aruco == aruco)].tag.values[0]
        b.loc[:, ['x', 'y', 'z']] = qrdar.common.apply_rotation(np.linalg.inv(M), b)        
        ply_io.write_ply(os.path.join(odir, '{}.ply'.format(tag)), b[cols])
        print ('\tsaved branch to:', os.path.join(odir, '{}.ply'.format(tag)))

def read_pc(args):
    
    pc = qrdar.io.read_ply(args.pc)
    pc = pc[pc.dev <= 10]
    pc.loc[:, 'is_branch'] = True
    pc.loc[:, 'aruco'] = np.nan
    if args.verbose: print ("number of points:", len(pc))
    
    return pc
       

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--pc', type=str, help='path to point cloud')
    parser.add_argument('-t', '--translation', type=str, help='path to .csv with tag translation,\
                                                               this should have the form "name, project, code" \
                                                               where name is the branch name, project is the name\
                                                               of the file and code is the qrDAR number')
    parser.add_argument('-o', '--odir', type=str, help='output directory for branches')
    parser.add_argument('--bucket-height', type=float, default=.4, help='height of the bucket')
    parser.add_argument('--bucket-radius', type=float, default=.15, help='radius of the bucket')
    parser.add_argument('--verbose', action='store_true', help='print something')
    args = parser.parse_args()
    
    # path = '2019-07-26.012.riproject/ascii/2019-07-26.012.ply'
    project = os.path.split(args.pc)[1][:-4]

    # reading in translation will need to be edited
    # dependent on formatting etc.
    ctag = lambda row: '{}-{}-{}'.format(*row[['plot', 'treetag', 'light']])
    translation = pd.read_csv(args.translation)
    translation.rename(columns={c:c.lower() for c in translation.columns}, inplace=True)
    translation.loc[:, 'tag'] = translation.apply(ctag, axis=1)
    translation.tag = [t.replace('-nan', '') for t in translation.tag]
    translation = translation[translation.project == project]
    
    if args.verbose: print ('processing project:', args.pc)
    
    n_targets = len(translation[translation.project == project])
    expected = translation[translation.project == project].aruco.astype(int).values
    print('expecting targets:', n_targets)

    # read in branch scan
    pc = read_pc(args)

    ### read aruco targets ###
    target_centres = read_aruco2(pc, expected, verbose=args.verbose)
    
    ### identify ground ###
    pc, M = identify_ground2(pc, target_centres)

    ### find buckets ###
    pc, buket_centres = find_buckets(pc, target_centres, n_targets,
                                 bucket_height=args.bucket_height,
                                 bucket_radius=args.bucket_radius)

    ### isolate branches ###
    isolate_branches(pc, n_targets, translation, args.odir)
