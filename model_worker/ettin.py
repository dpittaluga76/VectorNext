"""Publisher Ettin scoring head after the ONNX token backbone. CPU float32."""
import json
import math
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file


class Head:
    def __init__(self, directory):
        directory = Path(directory)
        configs = [json.loads((directory/name/'config.json').read_bytes())
                   for name in ('1_Pooling', '2_Dense', '3_LayerNorm', '4_Dense')]
        pool, first, norm, last = configs
        if not (pool['pooling_mode'] == 'cls' and pool['embedding_dimension'] == 256
                and first['in_features'] == first['out_features'] == norm['dimension'] == last['in_features'] == 256
                and first['bias'] is False and last['bias'] is True and last['out_features'] == 1
                and first['activation_function'] == 'torch.nn.modules.activation.GELU'
                and last['activation_function'] == 'torch.nn.modules.linear.Identity'):
            raise ValueError('unsupported Ettin scoring head configuration')
        self.first, self.norm, self.last = [load_file(str(directory/name/'model.safetensors'))
                                           for name in ('2_Dense', '3_LayerNorm', '4_Dense')]
        # Keys/shapes are checked explicitly rather than treating a backbone as logits.
        for weights, shapes in ((self.first, {'linear.weight': (256,256)}),
                                (self.norm, {'norm.weight': (256,), 'norm.bias': (256,)}),
                                (self.last, {'linear.weight': (1,256), 'linear.bias': (1,)})):
            if set(weights) != set(shapes) or any(weights[k].shape != shape or not np.isfinite(weights[k]).all()
                                                  for k,shape in shapes.items()):
                raise ValueError('invalid Ettin scoring head weights')

    def __call__(self, hidden):
        if hidden.ndim != 3 or hidden.shape[1] == 0 or hidden.shape[2] != 256:
            raise ValueError('Ettin requires token hidden states')
        x = hidden[:,0,:] @ self.first['linear.weight'].T
        # PyTorch GELU's default approximate="none", not the tanh approximation.
        erf = np.vectorize(math.erf, otypes=[np.float32])
        x = (.5*x*(1+erf(x/np.float32(math.sqrt(2))))).astype(np.float32)
        x = (x-x.mean(axis=-1,keepdims=True))/np.sqrt(x.var(axis=-1,keepdims=True)+np.float32(1e-5))
        x = x*self.norm['norm.weight']+self.norm['norm.bias']
        return (x @ self.last['linear.weight'].T + self.last['linear.bias']).reshape(-1).astype(np.float32)
