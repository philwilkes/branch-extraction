<div class="cell markdown">

# Reconstructing branches from TLS scans

This repository runs through the steps used to reconstruct branches from
TLS scans.

Outlined below are the steps required used in an upcoming paper.

#### 1\. [Branch scanning](#branch-scanning)

#### 2\. [Project registration](#project-registration)

#### 3\. [Branch extraction](#branch-extraction)

#### 4\. [Filtering](#filtering)

#### 5\. [QSM fitting](#qsm-fitting)

Some of the steps are very specific to scanning with a RIEGL TLS;
however, these can be modified and tips to do so are included.

</div>

<div class="cell markdown">

<a id='branch-scanning'></a>

## 1\. Branch Scanning

Between 1 - 6 branches (dependent on branch size) were arranged in a
group, orientated so that they would not touch each other or the ground,
and scanned simultaneously. Branches were secured in the end of metal
tubing and placed in buckets of sand to minimise movement. [qrDAR
fiducial markers](https://github.com/philwilkes/qrdar) (akin to QR
codes) were placed on the floor to allow identification of each branch
in post-processing. The markers include a pattern of 4 retroreflective
stickers (10 mm diameter) which were used to co-register scans.

Between 4 - 6 scan positions (collectively known as a project), located
around the branches, were used to capture each set of branches. At each
position a single scan was performed with an angular resolution of
0.02\(^\circ\)

Branch scanning was done indoors to minimise the impact of wind which
branch tips are *very* sensitive too.

</div>

<div class="cell markdown">

<a id='project-registration'></a>

## 2\. Project registration

<b><i>This section is quite specific to using a RIEGL scanner and the
RiSCAN PRO software. At the end we require individual scans to be
registered into a single point cloud with (at a minimum) \[X Y Z
scan\_pos reflectance\] fields.</b></i>

#### 1\. Identify locations of reflective dots on qrDAR markers

Before importing scans into a project we want to identify the reflective
dots on the qrDAR markers as coarse registration tie-points. This will
require the installation of
[qrDAR](https://github.com/philwilkes/qrdar). We will also need to
convert our `.rxp` files to another format (ideally `.ply`). One options
is to use PDAL<sup>[1](#notes)</sup>, see `./pdal` for a pipeline. Other
options include using PCL.

If using PDAL, a loop<sup>[2](#notes)</sup> can be used to convert all
scans in a project to `.ply`

    mkdir ply
    cd ply
    for rxp in $(ls ../ScanPos*/??????_??????.rxp); 
        do pdal pipeline pdal/rxp2ply.json --readers.rxp.filename $rxp --writers.ply.filename ${rxp%.*}.ply; 
    done

Once scans are converted to `.ply` run

    python python/find_dots.py <riproject_dir>

This will generate a `./stickers` directory containg text files with
sticker locations

#### 2\. Create .riproject

This step requires RiSCAN Pro (tested on version 2.9) and is therefore
run on a Windows machine. First you will need to create a blank project
(`blank.RiSCAN`), this is used a basis to insert your data into.

Once you have creeated a blank project run

    python python\create_riscan.py --riproject C:\path\to\XXXX-XX-XX.XXX.riproject 
                                   --blank C:\path\to\blank.RiSCAN

#### 3\. Open the created project and register scans as normal

Now open the created project and register as normal. Tie points will
have been populated so no need to search for these (although sometimes
not always found) and scans has already been rotated to the correct
orienation.

<i>To make subsequent processing easier, select approximately the points
that will be required for further processing i.e. a polygon that
includes all branches, codes and some of the floor.</i>

Once registered, export scans as individual scans in .ascii format with
the fields PID, X, Y, Z, Deviation, Reflectance and <u>Selected</u>
fields to the `/ascii` directory (this will have been made when creating
.RiSCAN project). Also export the SOP rotation matrix in `.dat` format
to the `/matrix` directory.

#### 4\. Combine scans into a single point cloud

This step is necessary as it (1) removes all points that were not
selected (see previous step) and (2) populates a scan position field. To
combine scans run

    python python/combine_scans.py /path/to/XXXX-XX-XX.XXX.riproject

</div>

<div class="cell markdown">

<a id='branch-extraction'></a>

## 3\. Branch extraction

Once you have generated a single point cloud for a set of branches the
next step is to extract individual branches. A mapping of qrDAR code to
branch name is needed, this is provided in a .csv as

| project        |   name   | code |
| -------------- | :------: | ---: |
| 2020-01-01.001 | XXX-T123 |    1 |
| 2020-01-01.001 | XXX-T456 |    2 |
| 2020-01-01.001 | XXX-T789 |    3 |

Then run the python script

``` 
  -p PC, --pc PC        path to point cloud
  -t TRANSLATION, --translation TRANSLATION
                        path to .csv with tag translation, this should have the form "name, project, code" where name is the branch name, project is the name of the file and code is the qrDAR number
  -o ODIR, --odir ODIR  output directory for branches
  --bucket-height BUCKET_HEIGHT
                        height of the bucket
  --bucket-radius BUCKET_RADIUS
                        radius of the bucket
  --verbose             print something


python python/extract_branches.py -p ascii/<project-point-clod.ply \
                                  -t branch_translation.txt 
                                  -o /put/branches/here 
```

</div>

<div class="cell markdown">

<a id='filtering'></a>

## 4\. Filtering

Filtering of noisy points and poitns where the footprint centroid does
not interect the branch are removed.

``` 
  -p PC, --pc PC        path to point cloud
  -o ODIR, --odir ODIR  output directory for branches
  --suffix SUFFIX       file name suffix
  
  
python python/filter_branch.py -p XXX-T123.ply 
                               -o .
                               --suffix filtered
```

</div>

<div class="cell markdown">

<a id='qsm-fitting'></a>

## 5\. QSM fitting

There are a number of options for fitting a QSM

1.  treegraph was used for this paper
2.  TreeQSM is another popular option
3.  And their are many others....

</div>

<div class="cell markdown">

### Notes

<a id='notes'></a>

#### <sup>1</sup> Compliling PDAL with RiVLib

1.  Create a conda environment using `conda create -n pdal-install -c
    conda-forge gdal ninja cmake cxx-compiler laszip`
    
2.  Download the [PDAL current release](https://pdal.io/download.html#current-release-s) 

3.  Download the `rivlib-2_5_10-x86_64-linux-gcc9.zip` from the memebers
    area of the RIEGL website (make sure to get the gcc9 version). Unzip
    and add an environmental variable to point at the directory `export
    RiVLib_DIR=/path/to/rivlib-2_5_10-x86_64-linux-gcc9`

4.  Follow the [PDAL Unix
    Compilation](https://pdal.io/development/compilation/unix.html)
    notes. Before running cmake edit line 63 of `cmake/options.cmake` to
    `"Choose if RiVLib support should be built" True)`

<sup>2</sup> assumes you have pdal and the Jupyter directory in your
path

</div>
