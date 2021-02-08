import os
import sys
import glob
import pandas as pd
import ply_io

if __name__ == '__main__':

    project = sys.argv[1]
    name = os.path.split(project)[1]
    print ('processing project:', name)
    
    df = pd.DataFrame()

    for asc in glob.glob(os.path.join(project, 'ascii', '*.ascii')):
        
        scan_position = int(os.path.split(asc)[-1][7:10])
        print ('\tprocessing scan position:', scan_position)

        # read in scan
        tmp = pd.read_csv(asc, engine='c', dtype=float, error_bad_lines=False)
        column2column = {u'PID[]':'pid', u'Target Count[]':'tot_rtn', u'XYZ[0][m]':'x', u'XYZ[1][m]':'y', u'XYZ[2][m]':'z',
                         u'Deviation[]':'dev', u'Reflectance[dB]':'refl', u'Target Index[]':'rtn_N', u'Selected[]':'sel'}
        tmp.columns = tmp.columns.map(column2column)
        tmp = tmp[tmp.sel == 1]
        if len(tmp) == 0:
            raise Exception('len df == 0, were required points selected in RiSCAN')
        tmp.loc[:, 'sp'] = scan_position

        # calc distance
#         mat = np.loadtxt('../matrix/ScanPos00{}.DAT'.format(scan_position))
#         tmp.loc[:, 'rng'] = np.linalg.norm(tmp[['x', 'y', 'z']] - mat[:3, 3], axis=1)

        df = df.append(tmp)#[tmp.refl.between(-20, 10)])

    ply_io.write_ply(os.path.join(project, 'ascii',  name + '.ply'),  
                     df[[c for c in df.columns if isinstance(c, str)]])