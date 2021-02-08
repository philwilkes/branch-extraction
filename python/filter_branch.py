import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
import argparse
import os
import qrdar

def nn(df, N=2):
    
    nbrs = NearestNeighbors(n_neighbors=N).fit(df[['x', 'y', 'z']])
    distances, indices = nbrs.kneighbors(df[['x', 'y', 'z']])
    return distances [:, 1:]

def process_branch(B, length=.01):
    
#     z = np.array([ 0.56678771, -1.01735439,  0.385116  , -0.20265323,  0.51859418]) # min_refl * .5
#     z = np.array([ 1.13525084, -2.03837157,  0.77297953, -0.40612175,  1.03726599]) # no min

    z = np.array([ 0.76671585, -1.4157199 , -0.08149528,  0.8143358 ]) ### THIS ONE WAS USED
    p = np.poly1d(z)
    
    # filter high deviation points
    if 'dev' in B.columns:
        B = B[B.dev.between(0, 10)] 
    
    # fuzz filter
    # voxelise branches (length = 1 cm)
    B.loc[:, 'xx'] = (B.x / length).astype(int)
    B.loc[:, 'yy'] = (B.y / length).astype(int)
    B.loc[:, 'zz'] = (B.z / length).astype(int)
    voxels = B.groupby(['xx', 'yy', 'zz', 'sp']).x.count().reset_index(name='cnt')
    voxels.loc[:, 'id'] = range(len(voxels))
    B = pd.merge(B, voxels[['xx', 'yy', 'zz', 'id', 'cnt', 'sp']], on=['xx', 'yy', 'zz', 'sp'])

    ### filter fuzz
    for sp in B.sp.unique():
        b = B[B.sp == sp]
        b.loc[:, 'refl_pro'] = 10**(b.refl / 10.)        
        b.loc[:, 'max_refl'] = b.groupby(B.id).refl_pro.transform(np.quantile, .99)#.reset_index()
        b.loc[:, 'per_of_max'] = p(b.max_refl)
        b.loc[:, 'min_pro'] = (b.max_refl * b.per_of_max) 
        idx = b[b.refl_pro <= b.min_pro].index
        B = B[~B.index.isin(idx)] 

    # filter isolated points
    B.loc[:, 'NN'] = nn(B, N=10).mean(axis=1)
    B = B[B.NN < B.NN.mean() + B.NN.std()]
    

    return B

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--pc', type=str, required=True, help='path to point cloud')
    parser.add_argument('-o', '--odir', type=str, default='.', help='output directory for branches')
    parser.add_argument('--suffix', default='', help='file name suffix')
    args = parser.parse_args()
    
    pc = qrdar.io.read_ply(args.pc)
    b = process_branch(pc)
    qrdar.io.write_ply(os.path.join(args.odir, '{}{}.ply'.format(os.path.split(args.pc)[1][:-4], 
                                                               '' if len(args.suffix) == 0 else '.' + args.suffix)), 
                     b)
    