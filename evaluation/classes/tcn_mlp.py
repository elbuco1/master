import torch
import torch.nn as nn
import torch.nn.functional as f 
import random
import numpy as np 
# import torchvision
import imp
from torch.nn.utils import weight_norm
import collections
from evaluation.classes.tcn import TemporalConvNet

class TCN_MLP(nn.Module):
    def __init__(self,args):
        super(TCN_MLP, self).__init__()

        self.args = args

        self.device = args["device"]
        self.batch_size = args["batch_size"]
        self.num_inputs = args["num_inputs"]
        self.mlp_layers = args["mlp_layers"]
        self.output_size = args["output_size"]
        self.kernel_size = args["kernel_size"]
        self.dropout = args["dropout"]
        self.input_length = args["input_length"]
        self.output_length = args["output_length"]
        self.nb_conv_feat = args["nb_conv_feat"]
        self.nb_cat = args["nb_cat"]


        self.nb_temporal_blocks = self.__get_nb_blocks(self.input_length,self.kernel_size)        
        self.num_channels = [self.nb_conv_feat for _ in range(self.nb_temporal_blocks)]


        self.tcn = TemporalConvNet(self.device, self.num_inputs, self.num_channels, self.kernel_size, self.dropout)

      


        self.mlp = nn.Sequential()
        self.mlp.add_module("layer0",nn.Linear(self.input_length* self.num_channels[-1] ,self.mlp_layers[0]))
        self.mlp.add_module("relu0",  nn.ReLU())
        for i in range(1,len(self.mlp_layers)):
            self.mlp.add_module("layer{}".format(i),nn.Linear(self.mlp_layers[i-1],self.mlp_layers[i]))
            self.mlp.add_module("relu{}".format(i), nn.ReLU())
        


        # self.mlp.add_module("layer{}".format(len(mlp_layers)), nn.Linear(mlp_layers[-1],self.output_size* self.output_length) )
        self.predictor =  nn.Linear(self.mlp_layers[-1] + self.nb_cat,self.output_size* self.output_length) 


    def forward(self,x): # x: B,Tobs,I
        
        types = x[1]
        x = x[0]
        b,n,s,i = x.size()
        x = x.squeeze(1)
        x = x.permute(0,2,1) # x: B,I,Tobs
        
        conv_features = self.tcn(x) # B,num_channels[-1], T_obs
        conv_features = conv_features.permute(0,2,1)
        b,tobs,f = conv_features.size()
        conv_features = conv_features.contiguous().view(b,tobs*f) # B,num_channels[-1] * T_obs

        # if self.nb_cat > 0:
        #     conv_features = torch.cat([conv_features,types],dim = 1)
        # print(conv_features.size())
        y = self.mlp(conv_features)
        
        if self.nb_cat > 0:
            y = torch.cat([y,types],dim = 1)

        y = self.predictor(y)
        
        y = y.view(b, self.output_length,self.output_size).unsqueeze(1)     
        return y # B,1, T_pred, I

    def __get_nb_blocks(self,receptieve_field,kernel_size):
        nb_blocks = receptieve_field -1
        nb_blocks /= 2.0*(kernel_size - 1.0)
        nb_blocks += 1.0
        nb_blocks = np.log2(nb_blocks)
        nb_blocks = np.ceil(nb_blocks)

        return int(nb_blocks)




class ConvNet(nn.Module):
    def __init__(self,device, num_inputs, num_channels, kernel_size=2, dropout=0.2,stride = 1):
        super(ConvNet, self).__init__()
        self.device = device
        layers = []
        num_levels = len(num_channels)
        for i in range(num_levels):
            p = int(   float( (num_inputs*(stride -1) + kernel_size - stride))/ 2.0   )
            padding = (p,p+1)
            # print(padding)
            layers += [ nn.ConstantPad1d(padding, 0.) ]
            if i == 0:
                layers += [ nn.Conv1d(num_inputs ,num_channels[i],kernel_size,stride= stride)]
            else:
                layers += [ nn.Conv1d(num_channels[i-1] ,num_channels[i],kernel_size,stride= stride)]

          
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)