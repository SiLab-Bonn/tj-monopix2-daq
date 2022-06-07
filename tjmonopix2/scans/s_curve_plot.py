import tables as tb
import numpy as np
import matplotlib as ml
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

h5file = tb.open_file("20220602_131251_threshold_scan_interpreted.h5", mode="r", title='configuration_in')
print(h5file)

HistOcc = h5file.root.HistOcc

arr = np.asarray(HistOcc)
plt.imshow(arr[:,:,20])
plt.show()

def sigmoid(x, L ,x0, k, b):
    y = L / (1 + np.exp(-k*(x-x0))) + b
    return (y)

xdata=range(35,75,1)
xdata=[el*10.1 for el in xdata]
ydata=arr[0,0]

p0 = [max(ydata)-min(ydata), np.median(xdata),1,min(ydata)] # this is an mandatory initial guess

popt, pcov = curve_fit(sigmoid, xdata, ydata,p0, method='dogbox')

x = xdata
y = sigmoid(x, *popt)

plt.plot(xdata,arr[0,0], 'o')
plt.plot(x,y, label='fit')

plt.xlabel("Charge injected in e-")
plt.ylabel("#hits")

s_curve_x0 = np.zeros(shape=(512, 512),dtype='float')
print(s_curve_x0 )

xdata=range(40,80,1)
xdata=[el*10 for el in xdata]
for i in range(512):
    print(i)
    for j in range(512):
        if i<224:
            try:
                ydata=arr[i,j]

                p0 = [max(ydata)-min(ydata), np.median(xdata),1,min(ydata)] # this is an mandatory initial guess
                popt, pcov = curve_fit(sigmoid, xdata, ydata,p0, method='dogbox')
                s_curve_x0[i,j]=popt[1]

            except:
                #print(j)
                s_curve_x0[i,j]=0
        else:
            s_curve_x0[i,j]=0

print(np.shape(s_curve_x0))
print(s_curve_x0)

image=plt.imshow(s_curve_x0[:,:]/2)
cbar = plt.colorbar(image)
plt.clim(500, 700)
cbar.set_label('threshold [e-]')
plt.xlabel("col")
plt.ylabel("row")

flatt= s_curve_x0[:223,:].flatten(order='C')
flatt=[el/2 for el in flatt]
n, bins, patches = plt.hist(flatt, bins=100)
bins_centered=(bins[:-1] + bins[1:])/2
mean = sum(flatt)/len(flatt)
sigma = 50
peak=200000
def gaus(x,a,x0,sigma):
    return a*np.exp(-(x-x0)**2/(2*sigma**2))

popt,pcov = curve_fit(gaus,bins_centered,n,p0=[peak,mean,sigma])
print(popt)
plt.xlabel("threshold in e-")
plt.ylabel("#hits")
plt.plot(x,gaus(x,*popt),'ro:',label='fit')
plt.xlim(400,800)
plt.text(410, 20000, "const "+str(round(popt[0],2)), fontsize=12)
plt.text(410, 18000, "mean "+str(round(popt[1],2)), fontsize=12)
plt.text(410, 16000, "sigma "+str(round(popt[2],2)), fontsize=12)