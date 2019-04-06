import keras.backend as K
from keras.layers import Layer
from keras import initializers, regularizers, constraints

from utils import *
from AttentionWithContext import *


"""
    For sentence encoder, 
    input: 
        x == word vectors;
        u == mean of contextual sentence vectors from AttentionWithContext;
    output: 
        sent vector
"""

class SentMultiContextAttention(AttentionWithContext):
    """
    Example:
        model.add(LSTM(64, return_sequences=True))
        model.add(SentMultiContextAttention())
        # next add a Dense layer (for classification/regression) or whatever...
    """
    
    def build(self, input_shapes):
        assert len(input_shapes[0]) == 3
        assert len(input_shapes[1]) == 4
        input_shape = input_shapes[0]
        
        self.W = self.add_weight((input_shape[-1], input_shape[-1],),
                                 initializer=self.init,
                                 name='{}_W'.format(self.name),
                                 regularizer=self.W_regularizer,
                                 constraint=self.W_constraint)
        if self.bias:
            self.b = self.add_weight((input_shape[-1],),
                                     initializer='zero',
                                     name='{}_b'.format(self.name),
                                     regularizer=self.b_regularizer,
                                     constraint=self.b_constraint)

    
    def call(self, xs, mask=None):
        x = xs[0]  # (batch_size, sent_len, 2*n_units)
        # xs[1] with (batch_size, window_size, r, 2*n_units)
        u = K.mean(xs[1], axis=1)  # (batch_size, r, 2*n_units)
        u = K.permute_dimensions(u, (0, 2, 1))  # (batch_size, 2*n_units, r)
        uit = dot_product(x, self.W)  # (batch_size, sent_len, 2*n_units)
        
        if self.bias:
            uit += self.b
        
        uit = K.tanh(uit)  # (batch_size, sent_len, 2*n_units)
        # use batch_dot rather dot_product because u shape (?, 2*n_units), self.u shape (2*n_units,)
        ait = K.batch_dot(uit, u)  # (batch_size, sent_len, r)
        a = K.exp(ait)  # (batch_size, sent_len, r)
        
        # # apply mask after the exp. will be re-normalized next
        # if mask is not None:
        #     # Cast the mask to floatX to avoid float64 upcasting in theano
        #     a *= K.cast(mask, K.floatx())
        
        # in some cases especially in the early stages of training the sum may be almost zero
        # and this results in NaN's. A workaround is to add a very small positive number ε to the sum.
        # a /= K.cast(K.sum(a, axis=1, keepdims=True), K.floatx())
        a /= K.cast(K.sum(a, axis=1, keepdims=True) + K.epsilon(), K.floatx())  # (batch_size, sent_len, r)

        a = K.permute_dimensions(a, (0, 2, 1))  # (batch_size, r, sent_len)
        weighted_inputs = K.batch_dot(a, x)  # (batch_size, r, 2*n_units)
        
        # mean by r, output shape (batch_size, 2*n_units)
        if self.return_coefficients:
            return [K.mean(weighted_input, axis=1), a]
        else:
            return K.mean(weighted_input, axis=1)
    
    
    def compute_output_shape(self, input_shapes):
        input_shape = input_shapes[0]
        if self.return_coefficients:
            return [(input_shape[0], input_shape[-1]), (input_shape[0], input_shape[-1], 1)]
        else:
            return input_shape[0], input_shape[-1]
