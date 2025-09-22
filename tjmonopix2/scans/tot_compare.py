import numpy as np
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit
from scipy.stats import chi2

def p_value(chisq, ndof):
    p = chi2.cdf(chisq, ndof)
    if p > 0.5:
       p = 1.0 - p
    return p

def tot_f(x, a, b, c, t):
    return a*x + b - (c/(x-t))

def charge_f(y, a, b, c, t):
    d = np.sqrt(b**2 + 4*a*c + 2*a*b*t + a**2*t**2 - 2*b*y -2*a*t*y +y**2)
    d1 = (-b + a*t+ y + d) / (2*a)
    return d1

# Fit the function to the data
# p0 = (0.019, 4.85, 142., 0.)
# p1 = (0.019, 4.69, 136., 0)
# p2 = (0.023, 5.03, 153., 0)
p0 = (0.014, 7.278, 190.148, 1.810)
p1 = (0.014, 7.326, 196.943, 0.973)
p2 = (0.014, 7.663, 213.906, 0.)
p3 = (0.015, 7.418, 191.782, 2.882)
p4 = (0.015, 7.972, 225.379, 0)
p5 = (0.019, 7.422, 209.951, 0.)
p6 = (0.017, 8.049, 230.311, 0)

thr0 = charge_f(0., *p0)
thr1 = charge_f(0., *p1)
thr2 = charge_f(0., *p2)
thr3 = charge_f(0., *p3)
thr4 = charge_f(0., *p4)
thr5 = charge_f(0., *p5)
thr6 = charge_f(0., *p6)


print('THR estimate i.e Qinj calculated with ToT = 0')
print('THR_0 = %.1f DAC'  %thr0)
print('THR_1 = %.1f DAC'  %thr1)
print('THR_2 = %.1f DAC'  %thr2)
print('THR_3 = %.1f DAC'  %thr3)
print('THR_4 = %.1f DAC'  %thr4)
print('THR_5 = %.1f DAC'  %thr5)
print('THR_6 = %.1f DAC'  %thr6)

delta_charge = []  # Lista vuota
delta_charge_rel = []  # Lista vuota

for i in range(1, 128):
    delta = charge_f(i, *p0)-charge_f(i, *p1)
    delta_rel = delta/charge_f(i, *p1)
    delta_charge.append(delta)
    delta_charge_rel.append(delta_rel)

#Plot delta charge vs TOT
fig = plt.figure('delta_charge')
tot = np.linspace(0, 128, 1000)
#plt.plot(tot, (charge_f(tot, *p0)-charge_f(tot, *p1))/charge_f(tot, *p1), color='red', label='Delta_charge col290-230')
plt.plot(tot, 100*(charge_f(tot, *p0)-charge_f(tot, *p1))/charge_f(tot, *p1), color='red', label='Delta_charge col290-230')

plt.xlim(0, 128)
plt.ylim(-20, 50)
plt.ylabel('relative delta charge [%]')
plt.xlabel('TOT [25 ns]')
plt.title("relative delta Q vs TOT")
plt.grid(which='both', ls='dashed', color='gray')
plt.legend()
plt.savefig('delta-charge.pdf')
#plt.show()


# Crea figura con 2 subplot verticali
fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(6, 8), sharex=False)


#Plot TOT
#fig = plt.figure('TOT')
# dac = np.linspace(1,8000, 10000)


# --- TOT vs Q ---
dac = np.linspace(thr0, 8000, 1000)
axs[0].plot(dac, tot_f(dac, *p0),label='TOT col230')
axs[0].plot(dac, tot_f(dac, *p1),label='TOT col260')
axs[0].plot(dac, tot_f(dac, *p2),label='TOT col290')
axs[0].plot(dac, tot_f(dac, *p3),label='TOT col330')
axs[0].plot(dac, tot_f(dac, *p4),label='TOT col360')
axs[0].plot(dac, tot_f(dac, *p5),label='TOT col390')
axs[0].plot(dac, tot_f(dac, *p6),label='TOT col430')

axs[0].set_ylim(0, 50)
axs[0].set_xlim(0, 1000)

axs[0].set_xlabel('Q [DAC]')
axs[0].set_ylabel('TOT [25 ns]')
axs[0].set_title("TOT vs Q")
axs[0].grid(which='both', ls='dashed', color='gray')
axs[0].legend()
axs[0].text(400, 42, '$f(x)=a\cdot x + b - (c/(x-t))$',color='k', fontsize=14)
func_params = ['a', 'b', 'c', 't']
#for j, param in enumerate(p0):
#    plt.text(10, 35 - j * 5, f'{func_params[j]}={param:.3f} ± {np.sqrt(pcov_cal[j, j]):.3f}',color='k', fontsize=14)
 #  axs[0].text(10, 35 - j * 5, f'{func_params[j]}={param:.3f}',color='blue', fontsize=12)
#for j, param in enumerate(p1):
#    plt.text(10, 35 - j * 5, f'{func_params[j]}={param:.3f} ± {np.sqrt(pcov_cal[j, j]):.3f}',color='k', fontsize=14)
 #  axs[0].text(200, 35 - j * 5, f'{func_params[j]}={param:.3f}',color='red', fontsize=12)
#for j, param in enumerate(p2):
#    plt.text(10, 35 - j * 5, f'{func_params[j]}={param:.3f} ± {np.sqrt(pcov_cal[j, j]):.3f}',color='k', fontsize=14)
   #axs[0].text(400, 35 - j * 5, f'{func_params[j]}={param:.3f}',color='black', fontsize=12)




# --- Secondo subplot: Q vs TOT ---
tot = np.linspace(0, 128, 1000)
axs[1].plot(tot, charge_f(tot, *p0), label='Charge col230')
axs[1].plot(tot, charge_f(tot, *p1), label='Charge col260')
axs[1].plot(tot, charge_f(tot, *p2), label='Charge col290')
axs[1].plot(tot, charge_f(tot, *p3), label='Charge col330')
axs[1].plot(tot, charge_f(tot, *p4), label='Charge col360')
axs[1].plot(tot, charge_f(tot, *p5), label='Charge col390')
axs[1].plot(tot, charge_f(tot, *p6), label='Charge col430')
axs[1].set_xlim(0, 50)
axs[1].set_ylim(0, 1000)
axs[1].set_ylabel('Q [DAC]')
axs[1].set_xlabel('TOT [25 ns]')
axs[1].set_title("Q vs TOT")
axs[1].grid(which='both', ls='dashed', color='gray')
axs[1].legend()

# Save
plt.tight_layout()
plt.savefig('tot_charge_vertical.pdf')
#plt.show()
