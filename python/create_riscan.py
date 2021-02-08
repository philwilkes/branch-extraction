import os
import shutil
import glob
import json
import subprocess
import argparse
import numpy as np

def scanposition(ScanPos, ScanName, reflectors=""):
    
    return """
        <scanposition name="{0}" kind="PositionX" fold="{0}"><name>{0}</name><observations name="OBSERVATIONS" kind="OBSERVATIONS" fold="OBSERVATIONS"/>
        <planefiles name="PLANEFILES" kind="PLANEFILES" fold="PLANEFILES"/>
        <polydata_objects name="POLYDATA" kind="POLYDATAOBJECTS" fold="POLYDATA"/><poseestimations name="POSEESTIMATIONS" kind="POSEESTIMATIONS" fold="POSEESTIMATIONS"/>
        <position_accuracy_horz>0</position_accuracy_horz><position_accuracy_vert>0</position_accuracy_vert><position_coordsys>4</position_coordsys><position_enabled>0</position_enabled><position_vector length="3"> 0 0 0 </position_vector>
        <ppm_air_pressure>1000</ppm_air_pressure><ppm_air_temperature>12</ppm_air_temperature><ppm_instrument>VZ-400</ppm_instrument>
        <ppm_moisture_pressure>8.4221</ppm_moisture_pressure><ppm_total_geometric_correction>0</ppm_total_geometric_correction><rdb2pointclouds name="POINTCLOUDS" kind="RDB2Pointclouds" fold="POINTCLOUDS"/>
        <registered>0</registered><scanposimages name="SCANPOSIMAGES" kind="SCANPOSIMAGES" fold="SCANPOSIMAGES"/><scanposundistimages name="UNDISTORTED IMAGES" kind="SCANPOSUNDISTIMAGES" fold="SCANPOSUNDISTIMAGES"/>
        <scansequences name="SCANSEQUENCES" kind="SCANSEQUENCES" fold="SCANSEQUENCES"/>
        <singlescans name="SINGLESCANS" kind="SINGLESCANS" fold="SINGLESCANS"><scan name="{1}" kind="ScanAcquiredX"><beamfocus>0</beamfocus>
        <blurlimit>1</blurlimit>
        <colored>0</colored><commandport></commandport><dataport></dataport>
        <file>{1}.rxp</file><frame_count>1</frame_count>
        <instrument>VZ-400</instrument><laser_clock>0</laser_clock><laserattenuated>0</laserattenuated>
        <measurementprogram>HIGH SPEED</measurementprogram><measurementprogramid>1</measurementprogramid><motion>0</motion><mta_autocalc_enabled>-1</mta_autocalc_enabled><mta_estmax_scanrange>-1</mta_estmax_scanrange><mta_manual_fixed_zone>-1</mta_manual_fixed_zone><mta_manual_range_max>3000</mta_manual_range_max>
        <mta_manual_range_min>0</mta_manual_range_min>
        <name>{1}</name><numtargets>0</numtargets><phi_count>3963</phi_count>
        <phi_delta>0.019999999552965165</phi_delta>
        <phi_start>74.360000610351552</phi_start>
        <serialnumber>S0000000</serialnumber><settings></settings><shock_detected>0</shock_detected><shock_factor>0</shock_factor>
        <text></text><theta_count>5001</theta_count>
        <theta_delta>0.019999999552965165</theta_delta>
        <theta_start>30</theta_start><time></time><type>3</type>
        <wideninglensactivated>0</wideninglensactivated>
        </scan>
        </singlescans><sop name="SOP" kind="SOP"><freeze>0</freeze>
        <matrix rows="4" cols="4"> 0 0 1 0   0 -1 0 0   1 0 0 0   0 0 0 1   </matrix>
        </sop>
        <text></text><tiepointscans name="TIEPOINTSCANS" kind="TIEPOINTSCANS" fold="TIEPOINTSCANS"/>
        <tiltmount_position>-1</tiltmount_position><tol_socs name="TOL (SOCS)" kind="TOL_SOCS" fold="TIEOBJECTS"><active>1</active>
        </tol_socs>
        <tpl_socs name="TPL (SOCS)" kind="TPL_SOCS"><active>1</active>
        {2}
        </tpl_socs>
        <voxelfiles name="VOXELFILES" kind="VOXELFILES" fold="VOXELFILES"/>
        </scanposition>""".format(ScanPos, os.path.splitext(ScanName)[0], reflectors)

def reflector_string(ixyz):
    
    return """
          <tp_socs name="{0:.0f}" kind="TP_SOCSX"><accuracy length="3"> -1 -1 -1 </accuracy>
          <active>1</active><intensity>0</intensity>
          <name>{0}</name><pixels>0</pixels><reflectivity>-INF</reflectivity>
          <refltype>0</refltype>
          <vector length="3">{1} {2} {3}</vector>
          <view>1</view>
        </tp_socs>""".format(*ixyz)

def generate_tiepoints(reflector_dir, ScanPos):
    sticker_string = ""
    stickers = np.loadtxt(glob.glob(os.path.join(reflector_dir, '{}*'.format(ScanPos)))[0], skiprows=1)
    for st in stickers:
        sticker_string += reflector_string (st)

    return sticker_string

def run_rimta(target, Source, ScanPos, ScanName):

    # required so os.system can run command with space in path 
    os.chdir('C:\\Program Files\\Riegl_LMS\\RiSCAN_PRO\\')
    
    from os.path import expanduser
    home = expanduser("~")

    cmd = [r'rimta5.exe',
           r'--rdbsettings "{}\\AppData\\Roaming\\Riegl_LMS\\RiSCAN_PRO\\Conf\\rdbcreatesettings.json"'.format(home),
           r'--residualRxpPath "{}\\SCANS\\{}\\SINGLESCANS\\{}.residual.rxp"'.format(target, ScanPos, ScanName),
           r'--logDir "{}\\project.rdb\\SCANS\\{}\\SINGLESCANS\\{}"'.format(target, ScanPos, ScanName),
           r'--dumpPath "\\AppData\\Roaming\\Riegl_LMS\\RiSCAN_PRO\\Debug"'.format(home),
           r'--progress --threads 4 --nostatistics --nohousekeeping --watchdog --verbose --fixedZone 1',
           r'"{}.rxp"'.format(os.path.join(Source, ScanPos, ScanName)),
           r'"{}\\project.rdb\\SCANS\\{}\\SINGLESCANS\\{}\\{}.rdbx"'.format(target, ScanPos, ScanName, ScanName)]
    
    os.system(' '.join(cmd))
    
def create_riscan(Source, Blank, Target, reflector_dir):
    
    # add dirs for final product
    for p in [os.path.join(Source, 'ascii'), os.path.join(Source, 'matrix')]:
        if not os.path.isdir(p): os.makedirs(p)
            
    # copy template
    shutil.copytree(Blank, Target)
    os.chdir(Target)
    
    # number of scan positions
    scan_positions = glob.glob(os.path.join(Source, 'ScanPos*'))
    scan_numbers = {os.path.split(sp)[1]:os.path.split(glob.glob(os.path.join(sp, '??????_??????.rxp'))[-1])[1][:-4]
                     for sp in scan_positions}
    
#     return scan_numbers
    
    # create file structure and copy over scans
    for ScanPos, ScanName in scan_numbers.items():
        singlescan_dir = os.path.join(Target, 'SCANS', ScanPos, 'SINGLESCANS')
        os.makedirs(singlescan_dir)
        shutil.copyfile(os.path.join(Source, ScanPos, ScanName + '.rxp'), 
                        os.path.join(Target, 'SCANS', ScanPos, 'SINGLESCANS', ScanName + '.rxp'))
        
    # run rimta
    for ScanPos, ScanName in scan_numbers.items():
        run_rimta(Target, Source, ScanPos, ScanName)
        
    # write project file
    os.chdir(Target)
    os.rename('project.rsp', 'project.rsp.copy')

    with open('project.rsp', 'w') as wh:

        with open('project.rsp.copy', 'r') as fh:

            for line in fh.readlines():

                if "project name" in line:
                    line = line.replace('BLANK', os.path.split(Target)[1].split('.')[0])

                if line.strip().startswith('<ppm_air_pressure>'):
                    line = '<ppm_air_pressure>1000</ppm_air_pressure><ppm_air_temperature>12</ppm_air_temperature>\
                            <ppm_moisture_pressure>8.4221</ppm_moisture_pressure>\
                            <ppm_total_geometric_correction>0</ppm_total_geometric_correction>\
                            <project_epsg>EPSG::4978</project_epsg>\
                            <project_wkt>GEOCCS["WGS84 / Geocentric",\
                            DATUM["WGS84",SPHEROID["WGS84",6378137.000,298.257223563,AUTHORITY["EPSG","7030"]],\
                            AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0.0000000000000000,AUTHORITY["EPSG","8901"]],\
                            UNIT["Meter",1.00000000000000000000,AUTHORITY["EPSG","9001"]],AXIS["X",OTHER],AXIS["Y",EAST],\
                            AXIS["Z",NORTH],AUTHORITY["EPSG","4978"]]</project_wkt><scanpositions name="SCANS" kind="SCANS" \
                            fold="SCANS">'
                    wh.write(line)

                    # add scan positions
                    for ScanPos, ScanName in scan_numbers.items():
                        sticker_string = generate_tiepoints(reflector_dir, ScanName)
                        wh.write(scanposition(ScanPos, ScanName, sticker_string))
                    wh.write('</scanpositions>')
                    continue

                wh.write(line)
                
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--riproject', type=str, required=True, help='the riproject directory')
    parser.add_argument('--blank', type=str, required=True, help='location of empty project')
    parser.add_argument('--stickers', type=str, help='location of stickers text files, defaults to stickers \
                                                      inside .riproject')
    parser.add_argument('--target', type=str, help='location of output, defaults to same dir as input')
    args=parser.parse_args()
    
    create_riscan(Source=args.riproject,
                  Blank=args.blank,
                  Target=args.riproject.replace('.riproject', '.RiSCAN') if not args.target else args.target,
                  reflector_dir=os.path.join(args.riproject, 'stickers')if not args.stickers else args.stickers)
    
    