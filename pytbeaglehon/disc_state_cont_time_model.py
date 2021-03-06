#! /usr/bin/env python
# Copyright (c) 2010 by Mark T. Holder
# (see bottom of file)
"""
Wrapper around a discrete-state, continuous time model of character state change.
"""
from itertools import izip
from pytbeaglehon import get_logger, CachingFacets
from pytbeaglehon.parameter import Parameter, FloatParameter, MutableFloatParameter, ProbabilityVectorParameter
_LOG = get_logger(__name__)

_EMPTY_SET = set()

class DiscStateContTimeModel(object):
    def __init__(self, **kwargs):
        self._cmodel = kwargs.get('cmodel')
        self._char_type = kwargs.get('char_type')
        self._model_index = kwargs.get('model_index')
        self._calc_env = kwargs.get('calc_env')
        self.asrv = kwargs.get('asrv')
        self._owns_calc_env = False
        self._changed_params = set()
        self._q_mat = None
        self._q_mat_hash = None
        self._prev_asrv_hash = None
        self._asrv_hash = None
        self._total_state_hash = None
        self._last_asrv_rates_hash = None
        self._prev_state_hash = None
        self._num_states = None # only used if _char_type is None
        self._eigen_soln_wrapper = None
        self._state_freq_hash = None
        param_list = kwargs.get('param_list')
        if param_list is not None:
            for p in param_list:
                _LOG.debug("Model %s registering self as listener of parameter %s" % (str(self), str(p)))
                p.add_listener(self.param_changed)
        self._changed_params.add(None) # having a non-empty set assures that the q_mat will be recognized as dirty
    
    
    def prob_matrices(self, edge_length, eigen_soln_caching=None, prob_mat_caching=None, as_wrappers=False):
        """returns probability matrices for all rate categories for the model given 
        the edge length `edge_length` 
        """
        prob_wrapper_list = self.calc_prob_matrices(edge_length, eigen_soln_caching=eigen_soln_caching, prob_mat_caching=prob_mat_caching)
        return self._fetch_prob_matrices(prob_wrapper_list)

    def __str__(self):
        return 'DiscStateContTimeModel for %s with asrv=%s at %d' % (str(self.char_type), str(self.asrv), id(self))

    def calc_prob_matrices(self, edge_length, eigen_soln_caching=None, prob_mat_caching=None):
        '''Returns a list containing a transition probability matrix for each rate category.'''
        self._incarnate()
        return self._calc_prob_matrices(edge_length, eigen_soln_caching=eigen_soln_caching, prob_mat_caching=prob_mat_caching)
        

    def param_changed(self, p):
        '''Adds `p` to this list of changed_parameters.'''
        _LOG.debug("Model %s learned that %s changed." % (str(self), str(p)))
        if self._total_state_hash is not None:
            self._prev_state_hash = self._total_state_hash
        self._total_state_hash = None
        self._state_freq_hash = None
        self._changed_params.add(p)

    def get_char_type(self):
        return self._char_type
    char_type = property(get_char_type)

    def get_num_states(self):
        if self._char_type is None:
            return self._num_states
        return self._char_type.num_states
    num_states = property(get_num_states)

    def q_mat_is_dirty(self):
        return (self._changed_params != _EMPTY_SET)

    def asrv_is_dirty(self):
        if self.asrv is None:
            return False
        self._asrv_hash = self.asrv.state_hash
        return self._asrv_hash != self._prev_asrv_hash

    def calc_q_mat(self):
        raise NotImplementedError()

    def get_q_mat(self):
        if self.q_mat_is_dirty():
            self.calc_q_mat()
            self._changed_params.clear()
        return self._q_mat

    def set_q_mat(self, v):
        self._changed_params.clear()
        self._total_state_hash = None
        if v is None:
            self._changed_params.add(None) # having a non-empty set assures that the q_mat will be recognized as dirty    
            self._q_mat = None
        else:
            self._q_mat = tuple([tuple([float(i) for i in row]) for row in v])
    q_mat = property(get_q_mat, set_q_mat)
    
    def get_q_mat_hash(self):
        if self.q_mat_is_dirty():
            qm = self.q_mat
            _LOG.debug('generating hash for %s' % repr(qm))
            self._q_mat_hash = hash(qm)
        return self._q_mat_hash
    q_mat_hash = property(get_q_mat_hash)

    def get_state_hash(self):
        if  (self._total_state_hash is None) or  self.q_mat_is_dirty() or self.asrv_is_dirty():
            self._total_state_hash = hash((id(self), self.q_mat_hash, self._asrv_hash))
            if self._prev_asrv_hash != self._asrv_hash:
                self._prev_asrv_hash = self._asrv_hash
        return self._total_state_hash
    state_hash = property(get_state_hash)
    
    def convert_eigen_soln_caching(self, in_eigen_soln_caching):
        if in_eigen_soln_caching is None:
            return (CachingFacets.DO_NOT_SAVE,)
        return (in_eigen_soln_caching,)

    def convert_prob_mat_caching(self, in_prob_mat_caching):
        if in_prob_mat_caching is None:
            return (CachingFacets.DO_NOT_SAVE,)
        return (in_prob_mat_caching,)

    def _calc_prob_matrices(self, edge_length, eigen_soln_caching=None, prob_mat_caching=None):
        """Returns and an index and state list object which records where the probability matrices
        are stored in the LikeCalcEnvironment.
        """
        es_wrapper = self.get_eigen_soln(eigen_soln_caching=eigen_soln_caching)
        return self._calc_env.calc_prob_from_eigen(edge_length, 
                                         self.asrv,
                                         eigen_soln=es_wrapper,
                                         prob_mat_caching=self.convert_prob_mat_caching(prob_mat_caching))

    def get_eigen_soln(self, eigen_soln_caching=None):
        state_id = self.state_hash
        es_wrapper = self._calc_env.calc_eigen_soln(model=self, 
                                             model_state_hash=state_id,
                                             eigen_soln_caching=self.convert_eigen_soln_caching(eigen_soln_caching))
        self._eigen_soln_wrapper = es_wrapper
        return self._eigen_soln_wrapper
    eigen_soln = property(get_eigen_soln)
        
    def _fetch_prob_matrices(self, prob_wrapper_list):
        return self._calc_env.get_prob_matrices(prob_wrapper_list)


    def _incarnate(self):
        'Assures that there is a LikeCalcEnvironment associated with this object'
        if (self._cmodel is None) or (self._model_index is None) or (self._calc_env is None):
            if self.num_states is None:
                raise ValueError("DiscStateContTimeModel.num_states must be set before calculations can be performed")
            from pytbeaglehon.like_calc_environ import LikeCalcEnvironment
            self._calc_env = LikeCalcEnvironment(num_leaves=2,
                                                 num_patterns=1,
                                                 num_states=self.num_states,
                                                 num_state_code_arrays=2,
                                                 num_partials=1,
                                                 model_list=[self],
                                                 num_prob_matrices=1,
                                                 num_eigen_storage_structs=1,
                                                 num_rescalings_multipliers=0,
                                                 resource_index=-1)
            self._owns_calc_env = True
    def _reassign_environ(self, calc_env, model_index, cmodel, asrv=None):
        '''Associates the model instance with a new LikeCalcEnvironment

        `model_index` is the new index of this model in that environment
        `cmodel` is a reference to the C object that represents the model.
        '''
        if self._owns_calc_env:
            self._calc_env.release_resources()
            self._owns_calc_env = False
        self._calc_env = calc_env
        self._model_index = model_index
        self._cmodel = cmodel
        self._asrv = asrv
    def get_num_eigen_solutions(self):
        return 1

    def get_num_categories(self):
        a = self.asrv
        if a is None:
            return 1
        return a.num_categories
    num_rate_categories = property(get_num_categories)

    def get_all_submodels(self):
        return [self]
    submodels = property(get_all_submodels)        

    def get_num_prob_models(self):
        return 1
    num_prob_models = property(get_num_prob_models)
    def get_cmodel(self):
        return self._cmodel
    cmodel = property(get_cmodel)
    
    def transmit_category_weights(self):
        "Intended for interal use only -- passes category weights to likelihood calculator for integration of likelihood"
        es_wrapper = self._eigen_soln_wrapper
        if es_wrapper is None:
            raise ValueError("eigen solution must be calculated transmit_category_weights can be called")
        asrv = self.asrv
        if asrv is None:
            from pytbeaglehon.like_calc_environ import NONE_HASH
            w = (1.0, )
            wph = NONE_HASH
        else:
            w = asrv.probabilities
            wph = asrv.get_prob_hash()
        es_wrapper.transmit_category_weights(w, wph)

    def transmit_state_freq(self):
        "Intended for interal use only -- passes equilibrium state frequencies to likelihood calculator for integration of likelihood"
        es_wrapper = self._eigen_soln_wrapper
        if es_wrapper is None:
            raise ValueError("eigen solution must be calculated transmit_state_freq can be called")
        sf = self.state_freq
        sfh = self.state_freq_hash
        es_wrapper.transmit_state_freq(sf, sfh)

    def get_state_freq_hash(self):
        if self._state_freq_hash is None:
            assert(self._state_freq is not None)
            self._state_freq_hash = repr(self._state_freq)
        return self._state_freq_hash
    state_freq_hash = property(get_state_freq_hash)

class RevDiscStateContTimeModel(DiscStateContTimeModel):

    def __init__(self, **kwargs):
        """Initializes a model. 
        kwargs:
        `r_mat` must be a square matrix (list of lists of floats).  Diagonal
            elements will be ignored. The columns of this matrix will be 
            multiplied by their corresponding equilibirium frequencies.
        `r_upper` can be used instead of `r_mat.` It should correspond to the
            upper triangle of the R-matrix.
        `equil_freq` must be None a list of the equilibrium frequencies.
        """
        r_upper = kwargs.get('r_upper')
        r_mat = kwargs.get('r_mat')
        sf = kwargs.get('state_freq')
        self.normalize_rates = kwargs.get('normalize_rates', True) # adjust the qmat such that the mean flux is 1.0
        if r_upper:
            if r_mat:
                raise ValueError("r_mat or r_upper cannot both be specified")
            r_mat = _r_upper_to_r_mat(r_upper) 
            _LOG.debug('r_mat from r_upper (%s) is %s' % (str(r_upper), str(r_mat)))
        elif not r_mat:
            raise ValueError("Either r_mat or r_upper must be given")

        priv_mat = []
        param_set = set()
        for row in r_mat:
            priv_row = list(row)
            for n, cell in enumerate(row):
                try:
                    param_set.update(cell.parameters())
                except:
                    priv_row[n] = MutableFloatParameter(cell)
                
            priv_mat.append(tuple(priv_row))
        if sf is None:
            raise ValueError("State frequencies must be specified for a RevDiscStateContTimeModel")
        if isinstance(sf, ProbabilityVectorParameter):
            self._state_freq = sf
        else:
            priv_sf = list(sf)
            for cell in sf:
                try:
                    param_set.update(cell.parameters())
                    priv_sf.append(cell)
                except:
                    priv_sf.append(FloatParameter(cell))
            self._state_freq = ProbabilityVectorParameter(priv_sf)
        param_set.update(set(self._state_freq.parameters()))
        DiscStateContTimeModel.__init__(self, param_list=param_set, **kwargs)
        if r_mat:
            if self.num_states is None:
               self._num_states = len(r_mat)
            self._verify_r_mat(r_mat)
        else:
            raise ValueError("Either r_mat or r_upper must be specified")
        self._r_mat = tuple(priv_mat)



    def get_r_mat(self):
        "Accessor for R-matrix."
        return self._r_mat
    r_mat = property(get_r_mat)
    def get_r_upper(self):
        "Accessor for R-matrix."
        return _r_mat_to_r_upper(self._r_mat)
    r_upper = property(get_r_upper)
    
    def get_state_freq(self):
        "Accessor for state frequencies."
        return self._state_freq
    def set_state_freq(self, v):
        "Accessor for state frequencies."
        _LOG.debug("In RevDiscStateContTimeModel.set_state_freq")
        if isinstance(v, ProbabilityVectorParameter):
            self.substitute_parameter_instance(self._state_freq, v)
            self._state_freq = v
        else:
            self._state_freq.value = v
    state_freq = property(get_state_freq, set_state_freq)
    
    q_mat = property(DiscStateContTimeModel.get_q_mat)

        
    
    def calc_q_mat(self):
        """Uses self._state_freq and self._r_mat to refresh self._q_mat.
        
        As required by the current version of cdsctm_set_q_mat, the Q-matrix
            is rescaled such that each row sums to 0.0 and the weighted 
            average of the diagonal elements is -1.0 (with the weight being the
            associated equilibrium frequency)."""
        assert(self._state_freq is not None)
        _LOG.debug("in self.calc_q_mat: _r_mat = %s _state_freq = %s" % (repr(self._r_mat), str(self._state_freq)))
        ns = self.num_states
        qr = [0.0] * ns
        qm = [list(qr) for i in range(ns)]
        w_mat_sum = 0.0
        for i, rows in enumerate(izip(self._r_mat, self._state_freq)):
            r_row, sf = rows
            q_row = qm[i]
            row_sum = 0.0
            for j, to_state in enumerate(izip(r_row, self._state_freq)):
                r_val, stf = [float(p) for p in to_state]
                if i != j:
                    v = r_val * stf
                    assert(r_val >= 0.0)
                    assert(stf >= 0.0)
                    q_row[j] = v
                    row_sum += v
            q_row[i] = -row_sum
            w_mat_sum += row_sum*self._state_freq[i]
        if self.normalize_rates:
            for q_row in qm:
                for i in xrange(len(q_row)):
                    q_row[i] /= w_mat_sum
        self._q_mat = tuple([tuple(row) for row in qm])
        _LOG.debug("_q_mat = %s" % str(qm))
        return self._q_mat
    
    def _verify_eq_freq_len(self, equil_freq):
        "Raises a ValueError if `equil_freq` is not the correct length"
        nef = len(equil_freq)
        if nef != self._num_states:
            if nef != (1 + self._num_states):
                raise ValueError("The number of states in the r_mat and "\
                             "equil_freq must agree.")

    def _verify_r_mat(self, r_mat):
        """Raises a ValueError if `r_mat` is not the correct shape or has 
        negative values (other than on the diagonal).
        """
        for i, row in enumerate(r_mat):
            if len(row) != self.num_states:
                raise ValueError("The R-matrix must be square.")
            for j, val in enumerate(row):
                if i != j:
                    if val < 0.0:
                        raise ValueError("Off-diagonal elements of the "\
                                         "R-matrix cannot be negative.")
                    if abs(val - float(r_mat[j][i])) > 1.0e-6:
                        raise ValueError("R-matrix must be symmetric")
    def get_num_states(self):
        "Returns the number of states"
        return self._num_states

    def get_adjusted_brlens_list(self, b):
        return [b]

    def get_model_list(self):
        return [self]

    def get_model_probs(self):
        return (1.0,)

    def get_parameters(self):
        return self._parameters

    model_probs = property(get_model_probs)
    r_mat = property(get_r_mat)
    r_upper = property(get_r_upper)
    

    def get_state_freq_value(self):
        return self._state_freq.value
    def set_state_freq_value(self, v):
        self._state_freq.value = v
    state_freq_value = property(get_state_freq_value, set_state_freq_value)




# Specific models below here...
from pytbeaglehon.disc_char_type import *
class HKY85Model(RevDiscStateContTimeModel):
    def __init__(self, kappa, state_freq):
        dna = DNAType()
        if isinstance(kappa, Parameter):
            if kappa.name is None:
                kappa.name = 'kappa'
        else:
            kappa = FloatParameter(value=kappa, name='kappa')
        if isinstance(state_freq, Parameter):
            if state_freq.name is None:
                state_freq.name = 'base-frequency vector'
        else:
            if len(state_freq) != 4:
                raise ValueError("state_freq must be of length 4")
            state_freq = ProbabilityVectorParameter(state_freq, name='base-frequency vector')
        for s, p in izip(dna.states, state_freq):
            p.name = 'freq_' + s
        RevDiscStateContTimeModel.__init__(self, r_upper=[[1.0, kappa, 1.0], [1.0, kappa], [1.0]], state_freq=state_freq, char_type=dna)
        self._kappa = kappa
    def get_kappa(self):
        return self._kappa
    def set_kappa(self, v):
        if isinstance(v, Parameter):
            self.substitute_parameter_instance(self._kappa, v)
            self._kappa = v
        else:
            self._kappa.value = v
    kappa = property(get_kappa, set_kappa)
    def get_kappa(self):
        return self._kappa
    def set_kappa(self, v):
        if isinstance(v, Parameter):
            self.substitute_parameter_instance(self._kappa, v)
            self._kappa = v
        else:
            self._kappa.value = v
    kappa = property(get_kappa, set_kappa)
    def get_kappa_value(self):
        return self._kappa.value
    def set_kappa_value(self, v):
        self._kappa.value = v
    kappa_value = property(get_kappa_value, set_kappa_value)
    def __str__(self):
        return 'HKY85Model at %d' % id(self)
class Kimura2ParameterModel(HKY85Model):
    def __init__(self, kappa):
        sf = ProbabilityVectorParameter([.25, .25, .25, .25, ], name='base-frequency vector')
        HKY85Model.__init__(self, kappa=kappa, state_freq=sf)
    def __str__(self):
        return 'Kimura2ParameterModel at %d' % id(self)
    state_freq = property(RevDiscStateContTimeModel.get_state_freq)
    state_freq_value = property(RevDiscStateContTimeModel.get_state_freq_value)

class JukesCantorModel(Kimura2ParameterModel):
    def __init__(self):
        Kimura2ParameterModel.__init__(self, kappa=1.0)
    def __str__(self):
        return 'JukesCantorModel at %d' % id(self)
    kappa = property(HKY85Model.get_kappa)
    kappa_value = property(HKY85Model.get_kappa_value)
    

def _r_upper_to_r_mat(r_upper):
    """Convert the upper triangle of a symmetric matrix to the full matrix with 
    0.0 on the diagonal.
    """
    len_upper = len(r_upper)
    r_mat = []
    blank = [0.0]
    for i in xrange(len_upper):
        next_row = blank + r_upper[i]
        blank.append(0.0)
        for j in xrange(i):
            next_row[j] = r_upper[j][i-j-1]
        r_mat.append(next_row)
    for j in xrange(len_upper):
        blank[j] = r_upper[j][len_upper-j-1]
    r_mat.append(blank)
    return r_mat

def _r_mat_to_r_upper(r_mat):
    """Returns the upper triangle (list of lists) of a square matrix `r_mat`"""
    r_upper = []
    for i in xrange(len(r_mat)):
        r_upper.append(r_mat[i][i+1:])
    return r_upper


##############################################################################
##  pytbeaglehon phylogenetic likelihood caluclations using beaglelib.
##
##  Copyright 2010 Mark T. Holder
##  All rights reserved.
##
##  See "LICENSE.txt" for terms and conditions of usage.
##
##############################################################################
