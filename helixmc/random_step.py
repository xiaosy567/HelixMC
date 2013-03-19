#This file is part of HelixMC.
#    Copyright (C) 2013  Fang-Chieh Chou <fcchou@stanford.edu>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
import abc
from util import params2coords
from __init__ import random

#####Random base-pair step parameters generator classes#####
class RandomStepBase(object):
    """
    Base class for Random bp-step generator, for inheritence only.

    See Also
    --------
    RandomStepSimple : Simple random bp-step generator.
    RandomStepAgg : Random bp-step generator by aggregrating multiple independent bp-step generators.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self):
        return

    @abc.abstractmethod
    def __call__(self):
        return

    @abc.abstractproperty
    def params_avg(self):
        return

    @abc.abstractproperty
    def gaussian_sampling(self):
        return

class RandomStepSimple(RandomStepBase):
    '''
    Simple random bp-step generator, with option of picking random datasets from database or sample from a multivariate Gaussian
    built from the database.

    Parameters
    ----------
    params : ndarray, shape (N,6), optional
        Input base-pair step parameters. Usually obtained by analyzing the structures in PDB.
        Must be specified if params_cov and params_avg is not being input, or if gaussian_sampling is set to False.
        Order = [Shift, Slide, Rise, Tilt, Roll, Twist]
        Distance in unit of Angstroms, angle in unit of radians.
    params_cov : ndarray, shape (6,6), optional
        Covariance matrix of the multivariate Gaussian for step parameters. Used for Gaussian sampling.
    params_avg : ndarray, shape (6,6), optional
        Averages of the multivariate Gaussian for step parameters. Used for Gaussian sampling.
    gaussian_sampling : bool, optional
        Whether to sample assuming a multivariate Gaussian. Default is True.

    Attributes
    ----------
    gaussian_sampling : bool
    params_avg : ndarray
    params_cov : ndarray
        See the Parameters section.

    Raises
    ------
    ValueError
        If params is not specified, and either params_avg and params_cov are not specified.
        If params is not specified, but gaussian_sampling is set to False.

    See Also
    --------
    RandomStepBase : Base class for Random bp-step generator, for inheritence only.
    RandomStepAgg : Random bp-step generator by aggregrating multiple independent bp-step generators.
    '''
    def __init__(self, params=None, params_cov=None, params_avg=None, gaussian_sampling=True):
        self._params = params
        if params != None:
            self._params_avg = np.average( params, axis=0 )
            self._params_cov = np.cov( params, rowvar=0 )
        else:
            if params_avg == None or params_cov == None:
                raise ValueError('params_avg and params_cov are not specified.')
            self._params_cov = params_cov
            self._params_avg = params_avg
            self._o_list, self._R_list = params2coords( params )
            self._n_bp_step = params.shape[0]
        self.gaussian_sampling = gaussian_sampling

    @property
    def gaussian_sampling(self):
        return self._gaussian_sampling

    @gaussian_sampling.setter
    def gaussian_sampling(self, val):
        self._gaussian_sampling = val
        if val:
            self._max_cached_data = 20000
            self._idx = self._max_cached_data
        elif self._params == None:
            raise ValueError('params is not specified, but gaussian_sampling is set to False.')

    @property
    def params_avg(self):
        return self._params_avg

    @property
    def params_cov(self):
        return self._params_cov

    def __call__(self):
        '''
        Draw one random bp-step parameter set from the distribution.

        Returns
        -------
        params: ndarray, shape (6)
            Randomly generated bp-step parameter set.
        o : ndarray, shape (3)
            Corresponding bp-center for the 2nd bp of the bp-step (1st bp is at origin and oriented with the coordinate frame).
        R : ndarray, shape (3,3)
            Corresponding frame for the 2nd bp of the bp-step.
        '''
        if self._gaussian_sampling:
            self._idx += 1
            if self._idx >= self._max_cached_data:
                self._idx = 0
                self._cached_params = random.multivariate_normal( self._params_avg, self._params_cov, self._max_cached_data )
                self._o_list, self._R_list = params2coords( self._cached_params )
            return self._cached_params[self._idx], self._o_list[self._idx], self._R_list[self._idx]
        else:
            i = random.randint(self._n_bp_step)
            return self._params[i], self._o_list[i], self._R_list[i]

class RandomStepAgg(RandomStepBase):
    '''
    Random bp-step generator by aggregating multiple independent simple bp-step generators.
    Useful for sequence dependence simulations.

    Parameters
    ----------
    data_file : str, optional
        Pre-curated database file with sequence dependence in .npz format.
    gaussian_sampling : bool, optional
        Whether to sample assuming a multivariate Gaussian. Default is True.

    Attributes
    ----------
    gaussian_sampling : bool
        See the Parameters section.
    params_avg : ndarray
        Average values for the step parameters distribution.
    names : list
        List of all names of RandomStep in the aggregation.

    See Also
    --------
    RandomStepBase : Base class for Random bp-step generator, for inheritence only.
    RandomStepSimple : Simple random bp-step generator.
    '''
    def __init__(self, data_file = None, gaussian_sampling=True):
        self._names = []
        self._rand_list = []
        self.gaussian_sampling = gaussian_sampling
        if data_file != None:
            self.load_from_file( data_file )

    def load_from_file(self, data_file):
        '''
        Load data file in .npz format and append to the current aggregation.

        Parameters
        ----------
        data_file : str, optional
            Pre-curated database file with sequence dependence in .npz format.
        '''
        data = np.load(data_file)
        for name in data.files:
            self.append_random_step( name, RandomStepSimple( params=data[name], gaussian_sampling=self.gaussian_sampling ) )

    def append_random_step(self, name, random_step):
        '''
        Append one additional random bp-step generator to the aggregation.

        Parameters
        ----------
        name : str
            Name of the random bp-step generator.
        random_step : subclass of RandomStepBase
            The random bp-step generator to be added to the aggregation

        Raises
        ------
        TypeError
            If random_step does not belong to a subclass of RandomStepBase.
        ValueError
            If the input name already exists in self.names.
        '''
        if not isinstance( random_step, RandomStepBase ):
            raise TypeError('random_step does not belong to a subclass of RandomStepBase.')
        if name in self._names:
            raise ValueError('Input name already exists in self.names!!!')
        self._names.append( name )
        self._rand_list.append( random_step )

    def clear_all(self):
        'Clear all random bp-step generator in the aggregation.'
        self._names[:] = []
        self._rand_list[:] = []

    @property
    def gaussian_sampling(self):
        return self._gaussian_sampling

    @gaussian_sampling.setter
    def gaussian_sampling(self, val):
        self._gaussian_sampling = val
        for i in self._rand_list:
            i.gaussian_sampling = val

    @property
    def params_avg(self):
        params_list = np.empty( (len(self._rand_list),6) )
        for i, rand in enumerate(self._rand_list):
            params_list[i] = rand.params_avg
        return np.average(params_list, axis=0)

    @property
    def names(self):
        return self._names[:]

    def name2rand_idx(self, name):
        '''
        Get the index of a RandomStep object in rand_list from its name.

        Parameters
        ----------
        name : str
            Name of the RandomStep in the aggregation.

        Returns
        -------
        idx : int
            The corresponding index of the RandomStep object.
        '''
        return self._names.index(name)


    def __call__(self, idx=None, name=None):
        '''
        Draw one random bp-step parameter set from the distribution.
        Randomly select one generator in the aggregation and return its generated result if neither 'name' nor 'idx' is given.

        Parameters
        ----------
        idx : int
            Index of the requested random step generator. Overides the 'name' parameter is both specified.
        name : str
            Name of the requested random step generator.

        Returns
        -------
        params: ndarray, shape (6)
            Randomly generated bp-step parameter set.
        o : ndarray, shape (3)
            Corresponding bp-center for the 2nd bp of the bp-step (1st bp is at origin and oriented with the coordinate frame).
        R : ndarray, shape (3,3)
            Corresponding frame for the 2nd bp of the bp-step.
        '''
        if name == None and idx == None:
            return self._rand_list[ random.randint( len(self._rand_list) ) ]()
        elif idx != None:
            return self._rand_list[idx]()
        else:
            return self._rand_list[ self.name2rand_idx(name) ] ()
