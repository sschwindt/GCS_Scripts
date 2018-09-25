'''
Functionality to add:
    choose las or laz output
    check size of biggest tile to make sure small enough (1.5M pt limit)
    set default values for lasground_new params?
    clip structures step
    use veg polygon (if given) instead of inverse ground polygon to clip veg points
    check_use for files
'''

from Tkinter import *
from file_functions import *
import sys
import shutil
import os
import numpy as np
import logging
init_logger(__file__)

##########################
#first let's define some functions that will be helpful

#input directory containing .las/.laz files, outputs list of all .las/.laz filenames
def las_files(directory):
    '''returns list of all .las/.laz files in directory (at top level)'''
    l = []
    for name in os.listdir(directory):
        if name.endswith('.las') or name.endswith('.laz'):
            l.append(directory+name)
            
    return l

#input working directory for LAStools and directory containing .las/.laz files, creates a .txt file for LAStools containing list of .las/.laz file names and returns the name of the .txt file.
def lof_text(pwd, src):
    '''creates a .txt file in pwd (LAStools bin) containing a list of .las/.laz filenames from src directory'''
    filename = pwd+'file_list.txt'
    f = open(filename, 'w+')
    
    if type(src) == str:
        for i in las_files(src):
            f.write('%s\n'%i)
    else: 
        #this is the case when there are multiple source folders
        for i in [name for source in src for name in las_files(source)]:
            f.write('%s\n'%i)
    
    return filename

#input .las/.laz filename, outputs point density (after running lasinfo)
def pd(filename):
    '''returns point density from lasinfo output .txt file'''
    #name of txt output file from lasinfo
    filename = filename[:-4]+'.txt'
    f = open(filename, 'r')
    text = f.readlines()
    for line in text:
        if line.startswith('point density:'):
            d = line.split(' ')
            d = d[d.index('only')+1]
            return float(d)

#the main function that runs when 'run' button is clicked
def process_lidar(lastoolsdir,
                  lidardir,
                  ground_poly,
                  cores,
                  units_code,
                  coarse_step,
                  coarse_bulge,
                  coarse_spike,
                  coarse_down_spike,
                  coarse_offset,
                  fine_step,
                  fine_bulge,
                  fine_spike,
                  fine_down_spike,
                  fine_offset
                  ):
    '''Executes main LAStools processing workflow. See Word doc for more info.'''
    
    classes = ['01-Default',
               '02-Ground',
               '05-Vegetation',
               '06-Building'
               ]
    
    outdirs = ['00_separated',
               '00_declassified',
               '01_tiled',
               '02a_lasground_new_coarse',
               '02b_lasground_new_fine',
               '03a_lasheight_coarse',
               '03b_lasheight_fine',
               '04a_lasclassify_coarse',
               '04b_lasclassify_fine',
               '05a_lastile_rm_buffer_coarse',
               '05b_lastile_rm_buffer_fine',
               '06a_separated_coarse',
               '06b_separated_fine',
               '07a_ground_clipped_coarse',
               '07b_ground_clipped_fine',
               '08_ground_merged',
               '09_ground_rm_duplicates',
               '10_veg_new_merged',
               '11_veg_new_clipped',
               '12_veg_merged',
               '13_veg_rm_duplicates'
               ]

    
    #make new directories for output from each step in processing
    for outdir in outdirs:
        if os.path.isdir(lidardir+outdir) == False:
            os.mkdir(lidardir+outdir)

    if len(os.listdir(lidardir+outdirs[0])) != 0:
        msg = 'Output directories must initially be empty. Move or delete the data currently in output directories.'
        logging.error(msg)
        raise Exception(msg)

    
    #in each 'separated' folder, create subdirs for each class type
    sepdirs = [lidardir+'00_separated',
               lidardir+'06a_separated_coarse',
               lidardir+'06b_separated_fine'
               ]
    for sepdir in sepdirs:
        for class_type in classes:
            class_dir = sepdir+'/'+class_type
            if os.path.isdir(class_dir) == False:
                os.mkdir(class_dir)
    
    logging.info('Created directories for output data')
    
    ##################################
    #create declassified points

    logging.info('Declassifying copy of original point cloud...')
    
    #get list of filenames for original LiDAR data (all .las and .laz files in lidardir)
    lidar_files = []
    for path, subdirs, files in os.walk(lidardir):
        for name in files:
            if name.endswith('.las') or name.endswith('.laz'):
                lidar_files.append(path+'/'+name)

    if lidar_files == []:
        msg = 'No .las or .laz files in %s or its subdirectories'%lidardir
        logging.error(msg)
        raise Exception(msg)
    
    #copy original files into '00_declassified' folder
    for name in lidar_files:
        shutil.copyfile(name, lidardir+'00_declassified/'+os.path.basename(name))      
    
    #make list of files for LASTools to process
    lof = lof_text(lastoolsdir, lidardir+'00_declassified/')
    #call LAStools command to declassify points and get point density
    cmd('%slasinfo.exe -lof %s -set_classification 1 -otxt -cd'%(lastoolsdir, lof) )
    
    
    logging.info('OK')
    
    ########################
    #create tiling (max 1.5M pts per tile)

    logging.info('Creating tiling...')
    
    #get point density for each .las file
    ds = []
    for filename in las_files(lidardir+'00_declassified/'):
        ds.append(pd(filename))
    #use max point density out of all files to determine tile size
    max_d = max(ds)
    
    #width of square tile so we have max of 1.5M pts per tile
    #throw in another factor of 0.5 to make sure tiles will be small enough, round to nearest 10
    tile_size = round(0.5*np.sqrt((1.5*10**6)/max_d), -1)

    logging.info('Using tile size of %i'%tile_size)
    
    odir = lidardir+'01_tiled/'
    
    #call LAStools command to create tiling
    cmd('%slastile.exe -lof %s -cores %i -o tile.las -tile_size %i -buffer 5 -faf -odir %s -olas'%(lastoolsdir, lof, cores, tile_size, odir))
    
    #add check to make sure tiles are small enough?
    #spatially index before tiling when running in parallel?
    
    logging.info('OK')
    
    ########################
    #run lasground_new on coarse and fine settings

    logging.info('Running ground classification on coarse setting...')
    
    lof = lof_text(lastoolsdir, lidardir+'01_tiled/')
    
    odir = lidardir+'02a_lasground_new_coarse/'
            
    cmd('%slasground_new.exe -lof %s -cores %i %s -step %s -bulge %s -spike %s -down_spike %s -offset %s -hyper_fine -odir %s -olas'%(lastoolsdir,
                                                                                                                                            lof,
                                                                                                                                            cores,
                                                                                                                                            units_code,
                                                                                                                                            coarse_step,
                                                                                                                                            coarse_bulge,
                                                                                                                                            coarse_spike,
                                                                                                                                            coarse_down_spike,
                                                                                                                                            coarse_offset,
                                                                                                                                            odir
                                                                                                                                            )
              )
    
    logging.info('OK')
    
    logging.info('Running ground classification on fine setting...')
    
    odir = lidardir+'02b_lasground_new_fine/'
    
    cmd('%slasground_new.exe -lof %s -cores %i %s -step %s -bulge %s -spike %s -down_spike %s -offset %s -hyper_fine -odir %s -olas'%(lastoolsdir,
                                                                                                                                            lof,
                                                                                                                                            cores,
                                                                                                                                            units_code,
                                                                                                                                            fine_step,
                                                                                                                                            fine_bulge,
                                                                                                                                            fine_spike,
                                                                                                                                            fine_down_spike,
                                                                                                                                            fine_offset,
                                                                                                                                            odir
                                                                                                                                            )
              )
    
    logging.info('OK')
    
    ##########################
    #run lasheight on each data set

    logging.info('Measuring height above ground for non-ground points...')
    
    lof = lof_text(lastoolsdir, lidardir+'02a_lasground_new_coarse/')
    odir = lidardir+'03a_lasheight_coarse/'
    
    cmd('%slasheight.exe -lof %s -cores %i -odir %s -olas'%(lastoolsdir, lof, cores, odir))
    
    lof = lof_text(lastoolsdir, lidardir+'02b_lasground_new_fine/')
    odir = lidardir+'03b_lasheight_fine/'
    
    cmd('%slasheight.exe -lof %s -cores %i -odir %s -olas'%(lastoolsdir, lof, cores, odir))
    
    logging.info('OK')
    
    ##########################
    #run lasclassify on each data set

    logging.info('Classifying non-ground points on coarse setting...')
    
    lof = lof_text(lastoolsdir, lidardir+'03a_lasheight_coarse/')
    odir = lidardir+'04a_lasclassify_coarse/'
    
    cmd('%slasclassify.exe -lof %s -cores %i %s -odir %s -olas'%(lastoolsdir, lof, cores, units_code, odir))
    
    logging.info('OK')

    logging.info('Classifying non-ground points on fine setting...')
    
    lof = lof_text(lastoolsdir, lidardir+'03b_lasheight_fine/')
    odir = lidardir+'04b_lasclassify_fine/'
    
    cmd('%slasclassify.exe -lof %s -cores %i %s -odir %s -olas'%(lastoolsdir, lof, cores, units_code, odir))
    
    logging.info('OK')
    
    ##########################
    #remove tile buffers on each data set

    logging.info('Removing tile buffers...')
    
    lof = lof_text(lastoolsdir, lidardir+'04a_lasclassify_coarse/')
    odir = lidardir+'05a_lastile_rm_buffer_coarse/'
    
    cmd('%slastile.exe -lof %s -cores %i -remove_buffer -odir %s -olas'%(lastoolsdir, lof, cores, odir))
    
    lof = lof_text(lastoolsdir, lidardir+'04b_lasclassify_fine/')
    odir = lidardir+'05b_lastile_rm_buffer_fine/'
    
    cmd('%slastile.exe -lof %s -cores %i -remove_buffer -odir %s -olas'%(lastoolsdir, lof, cores, odir))
    
    logging.info('OK')
    
    ##########################
    #separate into files for each class type

    logging.info('Separating points by class type on coarse setting...')
    
    #coarse
    lof = lof_text(lastoolsdir, lidardir+'05a_lastile_rm_buffer_coarse/')
    
    for class_type in classes:
        odir = lidardir+'06a_separated_coarse'+'/'+class_type+'/'
        class_code = int(class_type.split('-')[0])
        cmd('%slas2las.exe -lof %s -cores %i -keep_classification %i -odir %s -olas'%(lastoolsdir, lof, cores, class_code, odir))
        
    logging.info('OK')

    logging.info('Separating points by class type on fine setting...')
    
    #fine
    lof = lof_text(lastoolsdir, lidardir+'05b_lastile_rm_buffer_fine/')
    
    for class_type in classes:
        odir = lidardir+'06b_separated_fine'+'/'+class_type+'/'
        class_code = int(class_type.split('-')[0])
        cmd('%slas2las.exe -lof %s -cores %i -keep_classification %i -odir %s -olas'%(lastoolsdir, lof, cores, class_code, odir))
    
    logging.info('OK')
    
    ##########################
    #clip ground data sets with ground polygon

    logging.info('Clipping ground points to inverse ground polygon on coarse setting...')
    
    #keep points outside ground polygon for coarse setting (-interior flag)
    lof = lof_text(lastoolsdir, lidardir+'06a_separated_coarse'+'/'+'02-Ground'+'/')
    odir = lidardir+'07a_ground_clipped_coarse/'
    
    cmd('%slasclip.exe -lof %s -cores %i -poly %s -interior -donuts -odir %s -olas'%(lastoolsdir, lof, cores, ground_poly, odir))

    logging.info('OK')
          
    logging.info('Clipping ground points to ground polygon on fine setting...')
    
    #keep points inside ground polygon for fine setting
    lof = lof_text(lastoolsdir, lidardir+'06b_separated_fine'+'/'+'02-Ground'+'/')
    odir = lidardir+'07b_ground_clipped_fine/'
    
    cmd('%slasclip.exe -lof %s -cores %i -poly %s -donuts -odir %s -olas'%(lastoolsdir, lof, cores, ground_poly, odir))
    
    logging.info('OK')
    
    ##########################
    #merge

    logging.info('Separating original data by class type...')
    
    #separate original data by class type
    filename = lastoolsdir+'file_list.txt'
    f = open(filename, 'w+')
    for i in lidar_files:
        f.write('%s\n'%i)
    lof = filename
    
    for class_type in classes:
        odir = lidardir+'00_separated'+'/'+class_type+'/'
        class_code = int(class_type.split('-')[0])
        cmd('%slas2las.exe -lof %s -cores %i -keep_classification %i -odir %s -olas'%(lastoolsdir, lof, cores, class_code, odir))

    logging.info('OK')

    logging.info('Merging new and original ground points...')
    
    #merge processed ground points with original data set ground points
    sources = [lidardir+'07a_ground_clipped_coarse/',lidardir+'07b_ground_clipped_fine/', lidardir+'00_separated'+'/'+'02-Ground'+'/']
    lof = lof_text(lastoolsdir, sources)
    odir = lidardir+'08_ground_merged/'
    
    cmd('%slastile.exe -lof %s -cores %i -o tile.las -tile_size %i -faf -odir %s -olas'%(lastoolsdir, lof, cores, tile_size, odir))
    
    logging.info('OK')
    
    ##########################
    #remove duplicate ground points

    logging.info('Removing duplicate ground points...')
    
    lof = lof_text(lastoolsdir, lidardir+'08_ground_merged/')
    odir = lidardir+'09_ground_rm_duplicates/'
    
    cmd('%slasduplicate.exe -lof %s -cores %i -lowest_z -odir %s -olas'%(lastoolsdir, lof, cores, odir))
    
    logging.info('OK')
    
    ##########################
    #merge new veg points

    logging.info('Merging new vegetation points from coarse and fine run...')
    
    sources = [lidardir+'06a_separated_coarse'+'/'+'05-Vegetation'+'/', lidardir+'06b_separated_fine'+'/'+'05-Vegetation'+'/']
    lof = lof_text(lastoolsdir, sources)
    odir = lidardir+'10_veg_new_merged/'
    
    cmd('%slastile.exe -lof %s -cores %i -o tile.las -tile_size %i -faf -odir %s -olas'%(lastoolsdir, lof, cores, tile_size, odir))
    
    logging.info('OK')
    
    #########################
    #clip new veg points
    #keeping points outside the ground polygon

    logging.info('Clipping new vegetation points...')
    
    lof = lof_text(lastoolsdir, lidardir+'10_veg_new_merged/')
    odir = lidardir+'11_veg_new_clipped/'
    
    cmd('%slasclip.exe -lof %s -cores %i -poly %s -interior -donuts -odir %s -olas'%(lastoolsdir, lof, cores, ground_poly, odir))
    
    logging.info('OK')
    
    #########################
    #merge with original veg points

    logging.info('Merging new and original vegetation points...')
          
    sources = [lidardir+'11_veg_new_clipped/', lidardir+'00_separated'+'/'+'05-Vegetation'+'/']
    lof = lof_text(lastoolsdir, sources)
    odir = lidardir+'12_veg_merged/'
    
    cmd('%slastile.exe -lof %s -cores %i -o tile.las -tile_size %i -faf -odir %s -olas'%(lastoolsdir, lof, cores, tile_size, odir))
    
    logging.info('OK')
    
    #########################
    #remove duplicate veg points

    logging.info('Removing duplicate vegetation points...')
    
    lof = lof_text(lastoolsdir, lidardir+'12_veg_merged/')
    odir = lidardir+'13_veg_rm_duplicates/'
    
    cmd('%slasduplicate.exe -lof %s -cores %i -lowest_z -odir %s -olas'%(lastoolsdir, lof, cores, odir))
    
    logging.info('OK')
    
    logging.info('Processing finished.')
    
    return


#####################################################################

if __name__ == '__main__':

    #make the GUI window
    root = Tk()
    root.wm_title('LiDAR Reprocessing App (based on LAStools)')
    
    #specify relevant directories/files
    
    L1 = Label(root, text = 'LAStools /bin/ directory:')
    L1.grid(sticky = E, row = 0, column = 1)
    E1 = Entry(root, bd =5)
    E1.insert(END, '/'.join(sys.path[0].split('\\')[:-1])+'/')
    E1.grid(row = 0, column = 2)
    b1 = Button(root, text = 'Browse', command = lambda: browse(root, E1, select = 'folder'))
    b1.grid(sticky = W, row = 0, column = 3)
    
    L2 = Label(root, text = 'LiDAR data directory:')
    L2.grid(sticky = E, row = 1, column = 1)
    E2 = Entry(root, bd =5)
    E2.insert(END, '/'.join(sys.path[0].split('\\')[:-1])+'/')
    E2.grid(row = 1, column = 2)
    b2 = Button(root, text = 'Browse', command = lambda: browse(root, E2, select = 'folder'))
    b2.grid(sticky = W, row = 1, column = 3)
    
    L3 = Label(root, text = 'Ground area .shp file:')
    L3.grid(sticky = E, row = 2, column = 1)
    E3 = Entry(root, bd =5)
    E3.insert(END, '/'.join(sys.path[0].split('\\')[:-1])+'/')
    E3.grid(row = 2, column = 2)
    b3 = Button(root, text = 'Browse', command = lambda: browse(root, E3, select = 'file', ftypes = [('Shapefile','*.shp'),
                                                                                                      ('All files','*')]
                                                                )
                )
    b3.grid(sticky = W, row = 2, column = 3)
    
    
    #specify lasground_new parameters
    
    root.grid_rowconfigure(5, minsize=80)
    
    LC1 = Label(root, text = 'lasground_new coarse settings:')
    LC1.grid(row = 5, column = 0, columnspan = 2)
    
    L1a = Label(root, text = 'step size:')
    L1a.grid(sticky = E, row = 6)
    E1a = Entry(root, bd = 5)
    E1a.grid(row = 6, column = 1)
    
    L2a = Label(root, text = 'bulge:')
    L2a.grid(sticky = E, row = 7)
    E2a = Entry(root, bd = 5)
    E2a.grid(row = 7, column = 1)
    
    L3a = Label(root, text = 'spike:')
    L3a.grid(sticky = E, row = 8)
    E3a = Entry(root, bd = 5)
    E3a.grid(row = 8, column = 1)
    
    L4a = Label(root, text = 'down spike:')
    L4a.grid(sticky = E, row = 9)
    E4a = Entry(root, bd = 5)
    E4a.grid(row = 9, column = 1)
    
    L5a = Label(root, text = 'offset:')
    L5a.grid(sticky = E, row = 10)
    E5a = Entry(root, bd = 5)
    E5a.grid(row = 10, column = 1)

    
    LC2 = Label(root, text = 'lasground_new fine settings:')
    LC2.grid(row = 5, column = 2, columnspan = 2)
    
    L1b = Label(root, text = 'step size:')
    L1b.grid(sticky = E, row = 6, column = 2)
    E1b = Entry(root, bd = 5)
    E1b.grid(row = 6, column = 3)
    
    L2b = Label(root, text = 'bulge:')
    L2b.grid(sticky = E, row = 7, column = 2)
    E2b = Entry(root, bd = 5)
    E2b.grid(row = 7, column = 3)
    
    L3b = Label(root, text = 'spike:')
    L3b.grid(sticky = E, row = 8, column = 2)
    E3b = Entry(root, bd = 5)
    E3b.grid(row = 8, column = 3)
    
    L4b = Label(root, text = 'down spike:')
    L4b.grid(sticky = E, row = 9, column = 2)
    E4b = Entry(root, bd = 5)
    E4b.grid(row = 9, column = 3)
    
    L5b = Label(root, text = 'offset:')
    L5b.grid(sticky = E, row = 10, column = 2)
    E5b = Entry(root, bd = 5)
    E5b.grid(row = 10, column = 3)
    
    #specify units
    L5 = Label(root, text = 'Units')
    L5.grid(sticky = W, row = 11, column = 2)
    root.grid_rowconfigure(11, minsize=80)
    unit_var = StringVar()
    R5m = Radiobutton(root, text = 'Meters', variable = unit_var, value = ' ')
    R5m.grid(sticky = E, row = 12, column = 1)
    R5f = Radiobutton(root, text = 'US Feet', variable = unit_var, value = ' -feet -elevation_feet ')
    R5f.grid(row = 12, column = 2)
    unit_var.set(' ')
    
    #specify number of cores
    L4 = Label(root, text = 'Number of cores for processing')
    L4.grid(sticky = E, row = 13, column = 1, columnspan = 2)
    root.grid_rowconfigure(13, minsize=80)
    core_num = IntVar()
    R1 = Radiobutton(root, text = '1', variable = core_num, value = 1)
    R1.grid(sticky = E, row = 14, column = 1)
    R2 = Radiobutton(root, text = '2', variable = core_num, value = 2)
    R2.grid(row = 14, column = 2)
    R4 = Radiobutton(root, text = '4', variable = core_num, value = 4)
    R4.grid(sticky = W, row = 14, column = 3)
    R8 = Radiobutton(root, text = '8', variable = core_num, value = 8)
    R8.grid(sticky = E, row = 15, column = 1)
    R16 = Radiobutton(root, text = '16', variable = core_num, value = 16)
    R16.grid(row = 15, column = 2)
    R32 = Radiobutton(root, text = '32', variable = core_num, value = 32)
    R32.grid(sticky = W, row = 15, column = 3)
    core_num.set(16)
    
    
    
        
    #make 'Run' button in GUI to call the process_lidar() function
    b = Button(root, text = '    Run    ', command = lambda: process_lidar(lastoolsdir = E1.get(),
                                                                           lidardir = E2.get(),
                                                                           ground_poly = E3.get(),
                                                                           cores = core_num.get(),
                                                                           units_code = unit_var.get()[1:-1],
                                                                           coarse_step = E1a.get(),
                                                                           coarse_bulge = E2a.get(),
                                                                           coarse_spike = E3a.get(),
                                                                           coarse_down_spike = E4a.get(),
                                                                           coarse_offset = E5a.get(),
                                                                           fine_step = E1b.get(),
                                                                           fine_bulge = E2b.get(),
                                                                           fine_spike = E3b.get(),
                                                                           fine_down_spike = E4b.get(),
                                                                           fine_offset = E5b.get()
                                                                           )
               )

    b.grid(sticky = W, row = 17, column = 2)
    root.grid_rowconfigure(17, minsize=80)
    
    root.mainloop()
