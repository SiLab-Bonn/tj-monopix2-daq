import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os
import re

path = os.path.dirname(__file__)
path = os.path.join(path, "output_data")
#path = "/home/bellevtx01/vtx/tj-monopix2-daq/tjmonopix2/scans"


def plotHitmaps(dir_path, hist_occ):
    t=np.load(hist_occ)
    
    basename = os.path.basename(hist_occ)
    basename = re.findall("_(.*?)\.", basename)[0]  # extract the base (precisely: part between first '_' and '.')
    print("basename: ", basename)

    fig, ax= plt.subplots()
    image=plt.imshow(t)
    cbar = plt.colorbar(image)
    cbar.set_label('number injections')
    ax.set_xlabel('rows')
    ax.set_ylabel("column")
    #plt.show()
    plt.savefig(os.path.join(dir_path, "hitmap_"+basename+".png"))

    fig,ax = plt.subplots()
    t_list=t.ravel().tolist()
    ax.hist(t_list)
    ax.set_xlabel('number injections')
    ax.set_ylabel('number pixel')
    #plt.show()
    plt.savefig(os.path.join(dir_path, basename+".png"))


def plotTot(dir_path, hist_tot):
    tot=np.load(hist_tot)    
    
    basename = os.path.basename(hist_tot)
    basename = re.findall("_(.*?)\.", basename)[0]  # extract the base (precisely: part between first '_' and '.')
    print("basename: ", basename)

    fig, ax= plt.subplots()

    col , row = 100,100
    bins = np.linspace(1,127,128)
    heights = tot[col][row][0]
    #print("bins shape", bins.shape, "heights shape", heights.shape)
    mean = np.dot(bins,heights)/(np.sum(heights))

    ax.plot(tot[col][row][0])
    ax.set_xlabel('tot values uncalibrated')
    ax.set_ylabel("count")
    plt.figtext(0.5,0.85,"pixel {},{} mean tot={:.1f}".format(col,row,mean))
    #plt.show()
    plt.savefig(os.path.join(dir_path, basename+".png"))


    mean_tot = np.zeros((512,512))
    bins = np.linspace(1,127,128)

    for col in range(512):
	    for row in range(512):
		    #print(col)
		    #print(row)
		    
		    heights = tot[col][row][0]
		    if np.sum(heights) > 0:
			    mean_tot[col][row] = np.dot(bins,heights)/(np.sum(heights))
		    else:
			    mean_tot[col][row] = 0

    fig, ax= plt.subplots()
    image=plt.imshow(mean_tot)
    cbar = plt.colorbar(image)
    cbar.set_label('mean tot (uncalibrated)')
    ax.set_xlabel('rows')
    ax.set_ylabel("column")
    #plt.show()
    plt.savefig(os.path.join(dir_path, "totmap_"+basename+".png"))

    """
    fig, ax= plt.subplots()
    image=plt.imshow(tot)
    cbar = plt.colorbar(image)
    cbar.set_label('tot')
    ax.set_xlabel('rows')
    ax.set_ylabel("column")
    #plt.show()
    plt.savefig(path+"/hist_tot_map.png")
    """


hist_occ_files = glob.glob(path + '/analoge_hist_occ*.npy')
for f in hist_occ_files:
    print("plotting file: ", f)
    plotHitmaps(path, f)
    
#latest_hist_occ = sorted(hist_occ_files)[-1]

hist_tot_files = glob.glob(path + '/analoge_hist_tot*.npy')
for f in hist_tot_files:
    print("plotting file: ", f)
    plotTot(path, f)








