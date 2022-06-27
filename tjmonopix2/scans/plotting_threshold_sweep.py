import tables as tb
import numpy as np
import matplotlib as ml
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import os
from tqdm import tqdm
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import time

start = time()


# Getting the current date and time
dt = datetime.now()

start_row = [2,250,449,482]
end_row=[4,252,448,511]
FE_list = ['FE_normal','FE_CASC_normal','FE_CASC_HV','FE_HV']



path = "output_data_threshold_FE_normal_fullscan"

data_output_path = os.path.join(path,'threshold_scan')
Path(data_output_path).mkdir(parents=True, exist_ok=True)

reg_list=[]
FILES_BY_REG = defaultdict(list)
VALS_BY_REG = defaultdict(list)
with open(path + "/scan_threshold_sweep.txt") as ifs:
    for ln in ifs:
        file, x = ln.rsplit(maxsplit=1)
        file_name_split = file.split(os.sep)
        file_name = os.path.join(file_name_split[-3],file_name_split[-2], file_name_split[-1])
        reg, val = x.split("=")
        reg_list.append(reg)
        val = int(val)
        FILES_BY_REG[reg].append(path + "/"+ file_name)
        VALS_BY_REG[reg].append(val)
#print(FILES_BY_REG)
#print(VALS_BY_REG)
#print(reg_list)
reg_list = list(dict.fromkeys(reg_list))

def sigmoid(x, L ,x0, k, b):
        y = L / (1 + np.exp(-k*(x-x0)))+ b
        return (y)

def fit_s_curve(i,j, color=None,label=None):
    ydata=arr[i,j]
    p0 = [max(ydata)-min(ydata), xdata[min([(i, abs(ydata[i] - ((max(ydata) + min(ydata)) / 2))) for i in range(len(ydata))], key=lambda x: x[1])[0]] ,1,min(ydata)] # this is an mandatory initial guess
    popt, pcov = curve_fit(sigmoid, xdata, ydata,p0, method='dogbox')
    y = sigmoid(xdata, *popt)
    plt.plot(xdata,ydata, 'o', c=color)
    plt.plot(xdata,y, c=color)

    plt.xlabel("Charge injected in e-")
    plt.ylabel("#hits")
    plt.title('pixel {}, {}'.format(i,j))

def gaus(x,a,x0,sigma):
    return a*np.exp(-(x-x0)**2/(2*sigma**2))


for reg in tqdm(reg_list,desc='register loop'):


    scan_register=reg
    scan_range=list(range(VALS_BY_REG[reg][0],VALS_BY_REG[reg][-1]+int((VALS_BY_REG[reg][-1]-VALS_BY_REG[reg][0])/(len(VALS_BY_REG[reg])-1)),int((VALS_BY_REG[reg][-1]-VALS_BY_REG[reg][0])/(len(VALS_BY_REG[reg])-1))))
    #print(scan_range)
    file_list = FILES_BY_REG[reg]
    
    
    for FE,FE_name in enumerate(tqdm(FE_list, leave=False, desc='FE loop')):
        #print(FE)
        #print(FE_name)
        fig, (ax, cbar_ax) = plt.subplots(nrows=2, figsize=(10, 6), gridspec_kw={'height_ratios': [5, 1]})
        cmap = plt.cm.viridis
        norm = plt.Normalize(vmin=np.min(scan_range), vmax=np.max(scan_range))
        cb1 = ml.colorbar.ColorbarBase(cbar_ax, cmap=cmap, norm=norm, orientation='horizontal')
        plt.sca(ax)
        

        for i, file in enumerate(tqdm(file_list, leave=False, desc='plot s-curves for one pixel')):
            #print(i)
            h5file = tb.open_file(os.path.join(file+'_interpreted.h5'), mode="r", title='configuration_in')

            cfg = {str(a, encoding="utf8"): int(b) for a, b in h5file.root.configuration_in.scan.scan_config[:]}
            vh = cfg["VCAL_HIGH"]
            vl = range(cfg["VCAL_LOW_start"], cfg["VCAL_LOW_stop"], cfg["VCAL_LOW_step"])
            xdata=[vh-x for x in vl]
            xdata=[el*10.1 for el in xdata]

            HistOcc = h5file.root.HistOcc
            arr = np.asarray(HistOcc)
            fit_s_curve(start_row[FE],end_row[FE], color=cmap(norm(scan_range[i])),label=str(scan_range[i]))
            h5file.close()
        fig.tight_layout()
        fig.savefig(os.path.join(data_output_path, reg+'_s_curves_pixel_'+str(start_row[FE])+'_'+str(end_row[FE])+FE_name +'.png'))
        plt.close(fig)

        s_curve_x0 = np.zeros(shape=(512, 512,len(file_list)))
        s_curve_k = np.zeros(shape=(512, 512,len(file_list)))
        s_curve_L = np.zeros(shape=(512, 512,len(file_list)))
        s_curve_b = np.zeros(shape=(512, 512,len(file_list)))

        

        for k, file in enumerate(tqdm(file_list, leave=False, desc='S-curve fit per pixel')):
            h5file = tb.open_file(os.path.join(file+'_interpreted.h5'), mode="r", title='configuration_in')
            cfg = {str(a, encoding="utf8"): int(b) for a, b in h5file.root.configuration_in.scan.scan_config[:]}
            vh = cfg["VCAL_HIGH"]
            vl = range(cfg["VCAL_LOW_start"], cfg["VCAL_LOW_stop"], cfg["VCAL_LOW_step"])
            xdata=[vh-x for x in vl]
            xdata=[el*10.1 for el in xdata]
            HistOcc = h5file.root.HistOcc
            arr = np.asarray(HistOcc)

            for i in range(start_row[FE],end_row[FE],1):
                for j in range(512):
                    try:
                        ydata=arr[i,j]

                        p0 = [max(ydata)-min(ydata), xdata[min([(i, abs(ydata[i] - ((max(ydata) + min(ydata)) / 2))) for i in range(len(ydata))], key=lambda x: x[1])[0]] ,1,min(ydata)] # this is an mandatory initial guess
                        popt, pcov = curve_fit(sigmoid, xdata, ydata,p0, method='dogbox')
                        s_curve_L[i,j,k]=popt[0]
                        s_curve_x0[i,j,k]=popt[1]
                        s_curve_k[i,j,k]=1/popt[2]
                        s_curve_b[i,j,k]=popt[3]
                        #print('sucess')

                    except:
                        s_curve_x0[i,j]=0 
                        #print('fail')
            h5file.close()

        #dont really need this plot, plotting map for x0 of pixels for every step
        #for i in range(len(file_list)):
        #    plt.figure()
        #    image=plt.imshow(s_curve_x0[:,:,i])
        #    cbar = plt.colorbar(image)
        #    #plt.clim(500, 700)
        #    cbar.set_label('threshold [e-]')
        #    plt.xlabel("col")
        #    plt.ylabel("row")


        list_gauss_mean=[]
        list_gauss_sigma=[]
        for i in tqdm(range(len(file_list)), leave=False, desc='developement of the gauss fit'):
            fig = plt.figure()

            flatt= s_curve_x0[start_row[FE]:end_row[FE],:,i].flatten(order='C')

            n, bins, patches = plt.hist(flatt, bins=100)
            bins_centered=(bins[:-1] + bins[1:])/2
            if len(flatt)==0:
                guess_inital = [500, 1,20]
            else:   
                guess_inital = [500, sum(flatt)/len(flatt),20]
            #print(guess_inital)
            plt.xlabel("threshold in e-")
            plt.ylabel("#hits")
            plt.xlim(0,600)

            try:
                popt,pcov = curve_fit(gaus,bins_centered,n,p0=guess_inital)
                plt.plot(bins_centered,gaus(bins_centered,*popt),'ro:',label='fit')

                list_gauss_mean.append(popt[1])    
                list_gauss_sigma.append(popt[2])
                #print('gauss success')
            
            except:
                list_gauss_mean.append(0)    
                list_gauss_sigma.append(0)
                #print('gauss fail')

            #plt.show()
            fig.savefig(os.path.join(data_output_path, reg+str(scan_range[i])+'_gauss_'+FE_name +'.png'))
            plt.close(fig)

        fig=plt.figure()
        plt.errorbar(scan_range, list_gauss_mean, yerr=list_gauss_sigma, xerr=None)
        plt.xlabel(scan_register)
        plt.ylabel("threshold in e-")
        fig.savefig(os.path.join(data_output_path, reg+'_developement_'+FE_name +'.png'))
        plt.close(fig)
end = time()
print('time for plotting needed: ',end - start)
