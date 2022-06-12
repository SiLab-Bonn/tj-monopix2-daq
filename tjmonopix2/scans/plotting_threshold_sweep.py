import tables as tb
import numpy as np
import matplotlib as ml
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import os

path = "threshold_sweep"
file_list=['20220609_183251_threshold_scan',
           '20220609_183328_threshold_scan',
           '20220609_183405_threshold_scan',
           '20220609_183442_threshold_scan',
           '20220609_183518_threshold_scan',
           '20220609_183555_threshold_scan',
           '20220609_183631_threshold_scan',
           '20220609_183708_threshold_scan',
           '20220609_183744_threshold_scan',
           '20220609_183820_threshold_scan']
ITHR=list(range(25,75,5))

def sigmoid(x, L ,x0, k, b):
    y = L / (1 + np.exp(-k*(x-x0))) + b
    return (y)

def fit_s_curve(i,j, color=None,label=None):
    ydata=arr[i,j]
    p0 = [max(ydata)-min(ydata), xdata[min([(i, abs(ydata[i] - ((max(ydata) + min(ydata)) / 2))) for i in range(len(ydata))], key=lambda x: x[1])[0]] ,1,min(ydata)] # this is an mandatory initial guess
    popt, pcov = curve_fit(sigmoid, xdata, ydata,p0, method='dogbox')
    y = sigmoid(x, *popt)
    plt.plot(xdata,ydata, 'o', c=color)
    plt.plot(x,y, c=color)

    plt.xlabel("Charge injected in e-")
    plt.ylabel("#hits")
    
def gaus(x,a,x0,sigma):
    return a*np.exp(-(x-x0)**2/(2*sigma**2))
    

a=482

fig, (ax, cbar_ax) = plt.subplots(nrows=2, figsize=(10, 6), gridspec_kw={'height_ratios': [5, 1]})
cmap = plt.cm.viridis
norm = plt.Normalize(vmin=np.min(ITHR), vmax=np.max(ITHR))
cb1 = ml.colorbar.ColorbarBase(cbar_ax, cmap=cmap, norm=norm, orientation='horizontal')
plt.sca(ax)

for i, file in enumerate(file_list):
    h5file = tb.open_file(os.path.join(path,file+'_interpreted.h5'), mode="r", title='configuration_in')

    cfg = {str(a, encoding="utf8"): int(b) for a, b in h5file.root.configuration_in.scan.scan_config[:]}
    vh = cfg["VCAL_HIGH"]
    vl = range(cfg["VCAL_LOW_start"], cfg["VCAL_LOW_stop"], cfg["VCAL_LOW_step"])
    xdata=[vh-x for x in vl]
    xdata=[el*10.1 for el in xdata]

    HistOcc = h5file.root.HistOcc
    arr = np.asarray(HistOcc)
    fit_s_curve(a,a, color=cmap(norm(ITHR[i])),label=str(ITHR[i]))

s_curve_x0 = np.zeros(shape=(512, 512,len(file_list)))
s_curve_k = np.zeros(shape=(512, 512,len(file_list)))
s_curve_L = np.zeros(shape=(512, 512,len(file_list)))
s_curve_b = np.zeros(shape=(512, 512,len(file_list)))

for k, file in enumerate(file_list):
    h5file = tb.open_file(os.path.join(path,file+'_interpreted.h5'), mode="r", title='configuration_in')
    cfg = {str(a, encoding="utf8"): int(b) for a, b in h5file.root.configuration_in.scan.scan_config[:]}
    vh = cfg["VCAL_HIGH"]
    vl = range(cfg["VCAL_LOW_start"], cfg["VCAL_LOW_stop"], cfg["VCAL_LOW_step"])
    xdata=[vh-x for x in vl]
    xdata=[el*10.1 for el in xdata]
    HistOcc = h5file.root.HistOcc
    arr = np.asarray(HistOcc)
    
    for i in range(482,483,1):
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
for i in range(len(file_list)):
    plt.figure()
    
    flatt= s_curve_x0[a:a+1,:,i].flatten(order='C')

    n, bins, patches = plt.hist(flatt, bins=100)
    bins_centered=(bins[:-1] + bins[1:])/2
    guess_inital = [200000, sum(flatt)/len(flatt),50]
    

    popt,pcov = curve_fit(gaus,bins_centered,n,p0=guess_inital)
    plt.xlabel("threshold in e-")
    plt.ylabel("#hits")
    plt.plot(xdata,gaus(xdata,*popt),'ro:',label='fit')
    plt.xlim(0,600)
    list_gauss_mean.append(popt[1])    
    list_gauss_sigma.append(popt[2])


plt.figure()
plt.errorbar(ITHR, list_gauss_mean, yerr=list_gauss_sigma, xerr=None)
plt.xlabel("ITHR")
plt.ylabel("threshold in e-")
