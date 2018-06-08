from __future__ import print_function, division
import scipy as sp 
import tensorflow as tf
from scipy import stats
from scipy.integrate import cumtrapz
from scipy import interpolate
from matplotlib import pyplot as plt
import functools

#%% Constants
N_TIME = 100
N_HIDDEN = 12
N_INPUT = 2
N_ATTN  = 8 #< N_TIME how many previous steps to attend to
N_PLOTS = 4
N_OUTPUT = 2
LR_BASE = 1e-2
BATCH_SIZE = 52
ITRS = 800
REG = 1e-3

#Noise parameters
VNOISE_MU    = [1.0,5.0]
VNOISE_SCALE = [0.9,1.4]
XNOISE_SCALE1= [0.9,2.0]
XNOISE_SCALE2= [0.9,2.0]
XNOISE_MU1   = [0.0,0.0]
XNOISE_MU2   = [3.0,5.0]


#%%
# Create a bimodal gaussian distribution an implemnt a function to sample from it
class bimodal_gaussian(object):
    
    def __init__(self,loc1,loc2,scale1,scale2,xmin,xmax,npts=100,plot=False):
        #Import normal distribution
        pdf = sp.stats.norm.pdf
        cdf = sp.stats.norm.cdf
        
        #Sample spacec for plotting and interpolating
        x_eval = sp.linspace(xmin,xmax,npts)
            
        #Create a bimodal pdf
        bimodal_pdf = pdf(x_eval, loc=loc1, scale=scale1)*0.5 + \
                      pdf(x_eval, loc=loc2, scale=scale2)*0.5
                      
        bimodal_cdf = cdf(x_eval, loc=loc1, scale=scale1)*0.5 + \
                      cdf(x_eval, loc=loc2, scale=scale2)*0.5
        
        #Visualize the distirbution 
        if plot==True:
            plt.figure(figsize=(8,5))
            plt.title('Visualization of bimodal distribution')
            plt.ylim([0,1])
            plt.xlim([xmin,xmax])
            plt.grid(which='both')
            plt.plot(x_eval,bimodal_pdf, label='pdf')
            plt.plot(x_eval,bimodal_cdf, label='cdf')
            plt.legend()
            plt.show()
        
        #Make sure the cdf is bounded before interpolating the inverse
        bimodal_cdf[0]=0
        bimodal_cdf[-1]=1
        self.ppf = interpolate.interp1d(bimodal_cdf,x_eval)
        return
        
    #Sample the distribution for any given shape of input array (same as rand function)
    #ppf is an interpolation (approximate)
    def sample(self, *shape):
        samples = sp.random.rand(*shape)
        samples = self.ppf(samples)
        return samples
    
#Example of distribution
if __name__ == "__main__":        
    loc1 = 0.0
    scale1 = 0.3
    loc2 = 2
    scale2 = 0.5
    noise_dist = bimodal_gaussian(loc1,loc2,scale1,scale2,-5,5,100,plot=True)

#%% Generate true labels and noisy data for a given time-frame
t = sp.linspace(0,10,N_TIME)
def gen_sample(v, vnoise_sigma, xnoise_mu1,xnoise_mu2, xnoise_sigma1,xnoise_sigma2):
    true_vx = v*sp.ones_like(t) #Velocity is taken as constant
    #Trapezoidal rule integration of velocity into position
    true_x  = cumtrapz(true_vx,t) 
    true_x  = sp.hstack([[0],true_x])
    
    #Velocity only has Gaussian noise (this might have to be changed)
    noisy_vx = true_vx+sp.random.randn(*t.shape)*vnoise_sigma
    
    #Position has bimodal noise
    noise_dist = bimodal_gaussian(xnoise_mu1,xnoise_mu2,xnoise_sigma1,xnoise_sigma2,-5,5,100)
    noisy_x  = true_x+noise_dist.sample(*t.shape)
    
    return sp.stack([true_x,true_vx]).T, sp.stack([noisy_x,noisy_vx]).T

#%% Each sample will contain a trajectory of constant veloity and varying noise distribution
#Sample random noise distributions in a given range
N_SAMPLES  = BATCH_SIZE+N_PLOTS
vnoise_mu    = (VNOISE_MU[1]-VNOISE_MU[0])*sp.random.rand(N_SAMPLES) + VNOISE_MU[0]
vnoise_sigma = (VNOISE_SCALE[1]-VNOISE_SCALE[0])*sp.random.rand(N_SAMPLES)+VNOISE_SCALE[0]
xnoise_mu1   = (XNOISE_MU1[1]-XNOISE_MU1[0])*sp.random.rand(N_SAMPLES) + XNOISE_MU1[0]
xnoise_mu2   = (XNOISE_MU2[1]-XNOISE_MU2[0])*sp.random.rand(N_SAMPLES) + XNOISE_MU2[0]
xnoise_scale1 = (XNOISE_SCALE1[1]-XNOISE_SCALE1[0])*sp.random.rand(N_SAMPLES) + XNOISE_SCALE1[0]
xnoise_scale2 = (XNOISE_SCALE2[1]-XNOISE_SCALE2[0])*sp.random.rand(N_SAMPLES) + XNOISE_SCALE2[0]

batch_generation_inputs = zip(vnoise_mu,vnoise_sigma,xnoise_mu1,xnoise_mu2,xnoise_scale1,xnoise_scale2)

y_batch, x_batch = list(zip(*[gen_sample(*generator) for generator in batch_generation_inputs]))
batch_y= sp.stack(y_batch)
batch_x= sp.stack(x_batch)
print(batch_y.shape,batch_x.shape)

if False:
    plt.figure(figsize=(14,16))
    for batch_idx in range(N_PLOTS):
        noisy_x = batch_x[batch_idx,:,0]
        noisy_vx = batch_x[batch_idx,:,1]
        true_x = batch_y[batch_idx,:,0]
        true_vx = batch_y[batch_idx,:,1]
        
        plt.subplot(20+(N_PLOTS)*100 + batch_idx*2+1)
        if batch_idx == 0: plt.title('Location x')
        plt.plot(t,true_x,lw=2,label='true')
        plt.plot(t,noisy_x,lw=1,label=r'measured ($\mu =$ [%3.2f, %3.2f], $\sigma =$ [%3.2f, %3.2f])'\
                                                 %(xnoise_mu1[batch_idx],xnoise_mu2[batch_idx],\
                                                   xnoise_scale1[batch_idx],xnoise_scale2[batch_idx]))
        plt.grid(which='both')
        plt.ylabel('x[m]')
        plt.xlabel('time[s]')
        plt.legend()
        
        plt.subplot(20+(N_PLOTS)*100 + batch_idx*2+2)
        if batch_idx == 0: plt.title('Velocity x')
        plt.plot(t,true_vx,lw=2,label='true')
        plt.plot(t,noisy_vx,lw=1,label='measured')
        plt.ylabel('vx[m/s]')
        plt.xlabel('time[s]')
        plt.ylim([0,10])
        plt.grid(which='both')
        plt.legend()
        
    plt.savefig('1D_bimodal_example.png',dpi=200)

#%%
g1 = tf.Graph()
with g1.as_default():
    #input series placeholder
    x=tf.placeholder(dtype=tf.float32,shape=[None,N_TIME,N_INPUT])
    #input label placeholder
    y=tf.placeholder(dtype=tf.float32,shape=[None,N_TIME,N_INPUT])
    #Runtime vars
    batch_size=tf.placeholder(dtype=tf.int32,shape=())
    lr=tf.placeholder(dtype=tf.float32,shape=())
    
    
    #defining the network as stacked layers of LSTMs
    #lstm_layers =[tf.nn.rnn_cell.LSTMCell(size,forget_bias=0.9) for size in [N_HIDDEN]]
    #lstm_cell = tf.nn.rnn_cell.MultiRNNCell(lstm_layers)
    lstm_cell =tf.nn.rnn_cell.LSTMCell(N_HIDDEN,forget_bias=0.9)
    
    #Residual weapper
    #lstm_cell = tf.nn.rnn_cell.ResidualWrapper(lstm_cell)    
        
    #UNROLL
    lstm_inputs = tf.layers.Dense(N_HIDDEN, activation=tf.nn.relu,activity_regularizer=lambda z: REG*tf.nn.l2_loss(z))(x)
    outputs, state = tf.nn.dynamic_rnn(lstm_cell,lstm_inputs,dtype=tf.float32)

    #Output projection layer
    projection_layer = tf.layers.Dense(N_HIDDEN, activation=tf.nn.relu,activity_regularizer=lambda z: REG*tf.nn.l2_loss(z))(outputs)
    predictions = tf.layers.Dense(N_HIDDEN, activation=tf.nn.relu,activity_regularizer=lambda z: REG*tf.nn.l2_loss(z))(projection_layer)
    #Final output layer
    predictions = tf.layers.Dense(N_OUTPUT, activation=None,activity_regularizer=lambda z:REG*tf.nn.l2_loss(z))(predictions)
    print('Predictions:', predictions.shape)
    
    #loss_function
    loss= tf.reduce_mean((y-predictions)**2)
    #optimization
    opt=tf.train.AdamOptimizer(learning_rate=lr).minimize(loss)
    print('Compiled loss and trainer')
    
    #initialize variables
    init=tf.global_variables_initializer()
    print('Added initializer')

    #Count the trainable parameters 
    shapes = [functools.reduce(lambda x,y: x*y,variable.get_shape()) for variable in tf.trainable_variables()]
    print('Nparams: ', functools.reduce(lambda x,y: x+y, shapes))
#%% TRAINING
train_batch_x = batch_x[:BATCH_SIZE,:,:]
train_batch_y = batch_y[:BATCH_SIZE,:,:]
test_batch_x = batch_x[BATCH_SIZE:,:,:]
test_batch_y = batch_y[BATCH_SIZE:,:,:]        
with tf.Session(graph=g1) as sess:
    sess.run(init)
    itr=1
    learning_rate = LR_BASE
    while itr<ITRS:

        sess.run(opt, feed_dict={x: train_batch_x, y: train_batch_y, lr:learning_rate, batch_size: train_batch_x.shape[0]})
        
        if itr %20==0:
            learning_rate *= 0.95
            los,out=sess.run([loss,predictions],feed_dict={x:train_batch_x,y: train_batch_y,lr:learning_rate, batch_size: train_batch_x.shape[0]})
            print("For iter %i, learning rate %3.6f"%(itr, learning_rate))
            print("Loss ".ljust(12),los)
            los2,out2=sess.run([loss,predictions],feed_dict={x:test_batch_x,y: test_batch_y, batch_size:test_batch_x.shape[0]})
            print("DEV Loss ".ljust(12),los2)
            print("_"*80)

        itr=itr+1
        
    
    out  = sp.concatenate([out,out2],axis=0)
    
    

#%% Compute the EKF results
from KalmanFilterClass import LinearKalmanFilter1D, Data1D
batch_kalman = []
deltaT = sp.mean(t[1:] - t[0:-1])

P0     = sp.identity(2)*1.1
F0     = sp.array([[1, deltaT],\
                   [0, 1]])
H0     = sp.identity(2)
Q0     = sp.diagflat([0.0001,0.0001])
R0     = sp.diagflat([1.45,1.15])

for i in range(batch_y.shape[0]):
    data = Data1D(sp.squeeze(batch_x[i,:,0]),sp.squeeze(batch_x[i,:,1]),[])
    state0 = sp.array([batch_x[i,0,0], batch_x[i,0,1]]).T
    filter1b = LinearKalmanFilter1D(F0, H0, P0, Q0, R0, state0)
    kalman_data = filter1b.process_data(data)
    batch_kalman.append(sp.vstack([kalman_data.x[1:], kalman_data.vx[1:]]).T)
    
xk_batch = sp.stack(batch_kalman)
print(xk_batch.shape)
print('Kalman loss;'.ljust(12), sp.mean(pow(xk_batch[BATCH_SIZE:,:,:] - batch_y[BATCH_SIZE:,:,:],2)))
print(xk_batch.shape)
#%% Plot the fit    
plt.figure(figsize=(14,16))

for batch_idx in range(BATCH_SIZE,BATCH_SIZE+N_PLOTS):
    out_xc = sp.squeeze(out[batch_idx,:,0])
    out_vxc = sp.squeeze(out[batch_idx,:,1])
    
    noisy_xc  = batch_x[batch_idx,:,0]
    noisy_vxc = batch_x[batch_idx,:,1]
    
    true_xc = batch_y[batch_idx,:,0]
    true_vxc = batch_y[batch_idx,:,1]
    
    ekf_xc  = sp.squeeze(xk_batch[batch_idx,:,0])
    ekf_vxc = sp.squeeze(xk_batch[batch_idx,:,1])
    

    
    plot_idx = batch_idx-BATCH_SIZE
    plt.subplot(20+(N_PLOTS)*100 + plot_idx*2+1)
    if batch_idx == 0: plt.title('Location x')
    plt.plot(t,true_xc,lw=2,label='true')
    plt.plot(t,noisy_xc,lw=1,label='measured')
    plt.plot(t,ekf_xc,lw=1,label='Linear KF')
    plt.plot(t,out_xc,lw=1,label='LSTM')
    plt.grid(which='both')
    #plt.gca().equal()
    plt.ylabel('x[m]')
    plt.xlabel('time[s]')
    plt.legend()
    
    plt.subplot(20+(N_PLOTS)*100 + plot_idx*2+2)
    if batch_idx == 0: plt.title('Velocity Norm')
    plt.plot(t,true_vxc,lw=2,label='true')
    plt.plot(t,noisy_vxc,lw=1,label='measured')
    plt.plot(t,ekf_vxc,lw=1,label='Linear KF')
    plt.plot(t,out_vxc,lw=1,label='LSTM')
    plt.ylabel('vx[m/s]')
    plt.xlabel('time[s]')
    plt.grid(which='both')
    plt.legend()
    
plt.savefig('1D_bimodal_results_example.png',dpi=200)
    