#!python3
#
# Copyright (C) 2014-2015 Julius Susanto
#
# PYPOWER-Dynamics is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# PYPOWER-Dynamics is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PYPOWER-Dynamics. If not, see <http://www.gnu.org/licenses/>.

"""
PYPOWER-Dynamics
4th Order Synchronous Machine Model

"""

import numpy as np

class sym_order4:
    def __init__(self, filename, iopt):
        self.signals = {}
        self.states = {}
        self.states0 = {}
        self.dsteps = {}
        self.params = {}
        self.opt = iopt
        self.omega_n = 2 * np.pi * 50
        
        self.parser(filename)
        
        # Equivalent Norton impedance for Ybus modification
        self.Yg = (self.params['Ra'] - 1j * 0.5 * (self.params['Xdp'] + self.params['Xqp'])) / (self.params['Ra'] **2 + (self.params['Xdp'] * self.params['Xqp']))
    
    def parser(self, filename):
        """
        Parse a machine file (*.mach) and populate dictionary of parameters
        """
        f = open(filename, 'r')
        
        for line in f:
            if line[0] != '#' and line.strip() != '':   # Ignore comments and blank lines
                tokens = line.strip().split('=')
                if tokens[0].strip() == 'ID':
                    self.id = tokens[1].strip()
                elif tokens[0].strip() == 'GEN_NO':
                    self.gen_no = int(tokens[1].strip())
                else:
                    self.params[tokens[0].strip()] = float(tokens[1].strip())
                
        f.close()
    
    def initialise(self, vt0, S0):
        """
        Initialise machine signals and states based on load flow voltage and complex power injection
        """

        # Calculate initial armature current
        Ia0 =  np.conj(S0 / vt0)
        phi0 = np.angle(Ia0)
        
        # Calculate steady state machine emf (i.e. voltage behind synchronous reactance)
        Eq0 = vt0 + np.complex(self.params['Ra'],self.params['Xq']) * Ia0
        delta0 = np.angle(Eq0)
        
        # Convert currents to rotor reference frame
        Id0 = np.abs(Ia0) * np.sin(delta0 - phi0)
        Iq0 = np.abs(Ia0) * np.cos(delta0 - phi0)
        
        Vd0 = np.abs(vt0) * np.sin(delta0 - np.angle(vt0))
        Vq0 = np.abs(vt0) * np.cos(delta0 - np.angle(vt0))
        
        # Calculate machine state variables and Vfd
        Eqp0 = Vq0 + self.params['Ra'] * Iq0 + self.params['Xdp'] * Id0
        Edp0 = Vd0 + self.params['Ra'] * Id0 - self.params['Xqp'] * Iq0
        Vfd0 = np.abs(Eqp0) + (self.params['Xd'] - self.params['Xdp']) * Id0
        
        # Calculate active and reactive power
        p0 = (Vd0 + self.params['Ra']*Id0) * Id0 + (Vq0  + self.params['Ra']*Iq0) * Iq0
        q0 = Vq0 * Id0 - Vd0 * Iq0
        
        # Initialise signals, states and parameters        
        self.signals['Vfd'] = Vfd0
        self.signals['Id'] = Id0
        self.signals['Iq'] = Iq0
        self.signals['Vd'] = Vd0
        self.signals['Vq'] = Vq0
        self.signals['Vt'] = np.abs(vt0)
        self.signals['P'] = p0
        self.signals['Q'] = q0
        self.signals['Pm'] = p0
        
        self.states['omega'] = 1
        self.states['delta'] = delta0
        self.states['Eqp'] = Eqp0
        self.states['Edp'] = Edp0
        
        self.check_diffs()
        
    def calc_currents(self,vt):
        """
        Calculate machine current injections (in network reference frame)
        """
        # Calculate terminal voltage in dq reference frame
        Vd = np.abs(vt) * np.sin(self.states['delta'] - np.angle(vt))
        Vq = np.abs(vt) * np.cos(self.states['delta'] - np.angle(vt))
        
        # Calculate Id and Iq (Norton equivalent current injection in dq frame)
        if self.params['Ra'] > 0:
            Iq = (-self.params['Ra'] * (Vq-self.states['Eqp']) + self.params['Xdp'] * (Vd - self.states['Edp'])) / \
                    (self.params['Xdp'] * self.params['Xqp'] + self.params['Ra'] ** 2)
            Id = -(Vd - self.states['Edp'] - self.params['Xqp'] * Iq) / self.params['Ra']
        else:
            # Ra = 0 (or if Ra is negative, Ra is ignored)
            Id = (self.states['Eqp'] - Vq) / self.params['Xdp']
            Iq = (Vd - self.states['Edp']) / self.params['Xqp']
        
        # Calculate power output
        #p = Vd * Id + Vq * Iq       
        p = (Vd + self.params['Ra']*Id) * Id + (Vq  + self.params['Ra']*Iq) * Iq             
        q = Vq * Id - Vd * Iq
        
        # Calculate machine current injection (Norton equivalent current injection in network frame)
        #Im = (self.states['Eqp'] - 1j * self.states['Edp']) * np.exp(1j * (self.states['delta'])) / (1j * self.params['Xqp'])
        delta = self.states['delta']
        In = (Iq - 1j * Id) * np.exp(1j * (self.states['delta']))
        Im = In + self.Yg * vt
        
        """
        # Equivalent formulation
        Ir = np.sin(delta) * Id + np.cos(delta) * Iq
        Ii = -np.cos(delta) * Id + np.sin(delta) * Iq        
        Im = np.complex(Ir,Ii) + self.Yg * vt
        """
        
        # Update signals
        self.signals['Id'] = Id
        self.signals['Iq'] = Iq
        self.signals['Vd'] = Vd
        self.signals['Vq'] = Vq
        self.signals['P'] = p
        self.signals['Q'] = q
        self.signals['Vt'] = np.sqrt(Vd**2 + Vq**2)
        
        return Im
        
    def check_diffs(self):
        """
        Check if differential equations are zero (on initialisation)
        """
    
        # State variables
        Eqp_0 = self.states['Eqp']
        Edp_0 = self.states['Edp']
        
        Vfd = self.signals['Vfd']
        Id = self.signals['Id']
        Iq = self.signals['Iq']
        
        Xd = self.params['Xd']
        Xdp = self.params['Xdp']
        Td0p = self.params['Td0p']
        
        Xq = self.params['Xq']
        Xqp = self.params['Xqp']
        Tq0p = self.params['Tq0p']
        
        dEqp = (Vfd - (Xd - Xdp) * Id - Eqp_0) / Td0p
        dEdp = ((Xq - Xqp) * Iq - Edp_0) / Tq0p
        
        if round(dEdp,6) != 0 or round(dEqp,6) != 0:
            print('Warning: differential equations not zero on initialisation...')
            print('dEdp = ' + str(dEdp) + ', dEqp = ' + str(dEqp))
    
    def solve_step(self,h,dstep):
        """
        Solve machine differential equations for the next time step
        """
        
        # Initial state variables
        omega_0 = self.states['omega']
        delta_0 = self.states['delta']
        Eqp_0 = self.states['Eqp']
        Edp_0 = self.states['Edp']
        
        # Electrical differential equations
        p = [self.params['Xd'], self.params['Xdp'], self.params['Td0p']]
        yi = [self.signals['Vfd'], self.signals['Id']]
        f1 = (yi[0] - (p[0] - p[1]) * yi[1] - Eqp_0) / p[2]
        k_Eqp = h * f1
        
        p = [self.params['Xq'], self.params['Xqp'], self.params['Tq0p']]
        yi = self.signals['Iq']
        f2 = ((p[0] - p[1]) * yi - Edp_0) / p[2]
        k_Edp = h * f2
        
        # Swing equation
        f3 = 1/(2 * self.params['H']) * (self.signals['Pm'] - self.signals['P'])
        k_omega = h * f3
        
        f4 = self.omega_n * (omega_0 - 1)
        k_delta = h * f4
        
        if self.opt == 'mod_euler':
            # Modified Euler
            # Update state variables
            if dstep == 0:
                # Predictor step
                self.states['Eqp'] = Eqp_0 + k_Eqp
                self.dsteps['Eqp'] = [k_Eqp]
                self.states['Edp'] = Edp_0 + k_Edp
                self.dsteps['Edp'] = [k_Edp]
                self.states['omega'] = omega_0 + k_omega
                self.dsteps['omega'] = [k_omega]
                self.states['delta'] = delta_0 + k_delta
                self.dsteps['delta'] = [k_delta]
            else:
                # Corrector step
                self.states['Eqp'] = Eqp_0 + 0.5 * (k_Eqp - self.dsteps['Eqp'][0])
                self.states['Edp'] = Edp_0 + 0.5 * (k_Edp - self.dsteps['Edp'][0])
                self.states['omega'] = omega_0 + 0.5 * (k_omega - self.dsteps['omega'][0])     
                self.states['delta'] = delta_0 + 0.5 * (k_delta - self.dsteps['delta'][0])
        
        elif self.opt == 'runge_kutta':
            # 4th Order Runge-Kutta Method
            # Update state variables
            if dstep == 0:
                # Save initial states
                self.states0['omega'] = omega_0
                self.states0['delta'] = delta_0
                self.states0['Eqp'] = Eqp_0 
                self.states0['Edp'] = Edp_0
                
                self.states['Eqp'] = Eqp_0 + 0.5 * k_Eqp
                self.dsteps['Eqp'] = [k_Eqp]
                self.states['Edp'] = Edp_0 + 0.5 * k_Edp
                self.dsteps['Edp'] = [k_Edp]
                self.states['omega'] = omega_0 + 0.5 * k_omega
                self.dsteps['omega'] = [k_omega]            
                self.states['delta'] = delta_0 + 0.5 * k_delta
                self.dsteps['delta'] = [k_delta]
            elif dstep == 1:
                self.states['Eqp'] = Eqp_0 + 0.5 * k_Eqp
                self.dsteps['Eqp'].append(k_Eqp)
                self.states['Edp'] = Edp_0 + 0.5 * k_Edp
                self.dsteps['Edp'].append(k_Edp)
                self.states['omega'] = omega_0 + 0.5 * k_omega
                self.dsteps['omega'].append(k_omega)           
                self.states['delta'] = delta_0 + 0.5 * k_delta
                self.dsteps['delta'].append(k_delta)
            elif dstep == 2:
                self.states['Eqp'] = Eqp_0 + k_Eqp
                self.dsteps['Eqp'].append(k_Eqp)
                self.states['Edp'] = Edp_0 + k_Edp
                self.dsteps['Edp'].append(k_Edp)
                self.states['omega'] = omega_0 + k_omega
                self.dsteps['omega'].append(k_omega)           
                self.states['delta'] = delta_0 + k_delta
                self.dsteps['delta'].append(k_delta)
            elif dstep == 3:
                self.states['Eqp'] = self.states0['Eqp'] + 1/6 * (self.dsteps['Eqp'][0] + 2*self.dsteps['Eqp'][1] + 2*self.dsteps['Eqp'][2] + k_Eqp)
                self.states['Edp'] = self.states0['Edp'] + 1/6 * (self.dsteps['Edp'][0] + 2*self.dsteps['Edp'][1] + 2*self.dsteps['Edp'][2] + k_Edp)
                self.states['omega'] = self.states0['omega'] + 1/6 * (self.dsteps['omega'][0] + 2*self.dsteps['omega'][1] + 2*self.dsteps['omega'][2] + k_omega)
                self.states['delta'] = self.states0['delta'] + 1/6 * (self.dsteps['delta'][0] + 2*self.dsteps['delta'][1] + 2*self.dsteps['delta'][2] + k_delta)
   