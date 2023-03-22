import xarray as xr

from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from astrohack._classes.base_panel import panelkinds, irigid
from astrohack._classes.ring_panel import RingPanel
from astrohack._utils._constants import *
from astrohack._utils._conversion import _convert_to_db
from astrohack._utils._conversion import _convert_unit

lnbr = "\n"


class AntennaSurface:
    def __init__(self, inputxds, telescope, cutoff=None, pkind=None, crop=False, panel_margins=None):
        """
        Antenna Surface description capable of computing RMS, Gains, and fitting the surface to obtain screw adjustments
        Args:
            inputxds: Input xarray dataset
            telescope: Telescope object
            cutoff: fractional cutoff on the amplitude image to exclude regions with weak amplitude from the panel,
                    defaults to 20% if None
            pkind: Kind of panel surface fitting, if is None defaults to telescope default
            crop: Crop apertures to slightly larger frames than the antenna diameter
            panel_margins: Margin to be ignored at edges of panels when fitting, defaults to 20% if None
        """
        self._nullify()
        self.telescope = telescope
        computephase = self._read_xds(inputxds)

        if cutoff is None:
            self.cut = 0.2 * np.max(self.amplitude)
        else:
            self.cut = cutoff * np.max(self.amplitude)
        if pkind is None:
            self.panelkind = panelkinds[irigid]
        else:
            self.panelkind = pkind
        if panel_margins is None:
            self.panel_margins = 0.2
        else:
            self.panel_margins = panel_margins
        self.reso = self.telescope.diam / self.npoint

        if crop:
            self._crop_maps()

        if self.telescope.ringed:
            self._init_ringed()

        if computephase:
            self.phase = self._deviation_to_phase(self.deviation)
        else:
            self.deviation = self._phase_to_deviation(self.phase)

    def _read_xds(self, inputxds):
        """
        Read input XDS, distinguishing what is derived from AIPS data and what was created by astrohack.holog
        Args:
            inputxds: X array dataset
        """
        # Origin dependant Reading
        if inputxds.attrs['AIPS']:
            self.amplitude = inputxds["AMPLITUDE"].values
            self.deviation = inputxds["DEVIATION"].values
            self.npoint = inputxds.attrs['npoint']
            self.wavelength = inputxds.attrs['wavelength']
            self.amp_unit = inputxds.attrs['amp_unit']
            self.u_axis = inputxds.u.values
            self.v_axis = inputxds.v.values
            computephase = True
        else:
            if 'chan' in inputxds.dims:
                if inputxds.dims['chan'] != 1:
                    raise Exception("Only single channel holographies supported")
                self.wavelength = clight / inputxds.chan.values[0]
            else:
                self.wavelength = inputxds.attrs['wavelength']

            self.amplitude = inputxds["AMPLITUDE"].values[0, 0, 0, :, :]
            self.phase = inputxds["ANGLE"].values[0, 0, 0, :, :]

            self.npoint = np.sqrt(inputxds.dims['l']**2 + inputxds.dims['m']**2)
            self.amp_unit = 'V'
            self.u_axis = inputxds.u_prime.values * self.wavelength
            self.v_axis = inputxds.v_prime.values * self.wavelength
            computephase = False

        # Common elements
        self.unpix = self.u_axis.shape[0]
        self.vnpix = self.v_axis.shape[0]
        self.antenna_name = inputxds.attrs['ant_name']

        return computephase

    def _nullify(self):
        """
        Part of the initialization process, nullify the data objects to be used later
        """
        self.phase = None
        self.deviation = None
        self.residuals = None
        self.corrections = None
        self.phase_corrections = None
        self.phase_residuals = None
        self.solved = False
        self.ingains = np.nan
        self.ougains = np.nan
        self.in_rms = np.nan
        self.out_rms = np.nan

    def _init_ringed(self):
        """
        Do the proper method association for the case of a ringed antenna
        """
        if self.telescope.panel_numbering == 'ring, clockwise, top':
            self._panel_label = self._vla_panel_labeling
        elif self.telescope.panel_numbering == 'sector, counterclockwise, right':
            self._panel_label = self._alma_panel_labeling
        else:
            raise Exception("Unknown panel labeling: "+self.telescope.panel_numbering)
        self._build_polar()
        self._build_ring_panels()
        self._build_ring_mask()
        self.fetch_panel = self._fetch_panel_ringed
        self.compile_panel_points = self._compile_panel_points_ringed

    @staticmethod
    def _vla_panel_labeling(iring, ipanel):
        """
        Provide the correct panel label for VLA style panels
        Args:
            iring: Number of the ring the panel is in
            ipanel: Number of the panel in that ring clockwise from the top
        Returns:
            The proper label for the panel at iring, ipanel
        """
        return '{0:d}-{1:2d}'.format(iring+1, ipanel+1)

    def _alma_panel_labeling(self, iring, ipanel):
        """
        Provide the correct panel label for ALMA style panels, which is more complicated than VLA panels due to the
        implementation of panel sectors
        Args:
            iring: Number of the ring the panel is in
            ipanel: Number of the panel in that ring clockwise from the top

        Returns:
            The proper label for the panel at iring, ipanel
        """
        angle = twopi/self.telescope.npanel[iring]
        sector_angle = twopi/self.telescope.npanel[0]
        theta = twopi-(ipanel+0.5)*angle
        sector = int(((theta/sector_angle)+1+self.telescope.npanel[0]/4) % self.telescope.npanel[0])
        if sector == 0:
            sector = self.telescope.npanel[0]
        nppersec = self.telescope.npanel[iring]/self.telescope.npanel[0]
        jpanel = int(nppersec-(ipanel % nppersec))
        return '{0:1d}-{1:1d}{2:1d}'.format(sector, iring+1, jpanel)

    def _crop_maps(self, margin=0.025):
        """
        Crop the amplitude and phase/deviation maps to decrease that usage and speedup calculations
        Args:
            margin: How much margin should be left outside the dish diameter
        """
        edge = (0.5+margin)*self.telescope.diam
        iumin = np.argmax(self.u_axis > -edge)
        iumax = np.argmax(self.u_axis > edge)
        ivmin = np.argmax(self.v_axis > -edge)
        ivmax = np.argmax(self.v_axis > edge)
        self.unpix = iumax-iumin
        self.vnpix = ivmax-ivmin
        self.u_axis = self.u_axis[iumin:iumax]
        self.v_axis = self.v_axis[ivmin:ivmax]
        self.amplitude = self.amplitude[iumin:iumax, ivmin:ivmax]
        if self.phase is not None:
            self.phase = self.phase[iumin:iumax, ivmin:ivmax]
        if self.deviation is not None:
            self.deviation = self.deviation[iumin:iumax, ivmin:ivmax]

    def _phase_to_deviation(self, phase):
        """
        Transforms a phase map to a physical deviation map
        Args:
            phase: Input phase map

        Returns:
            Physical deviation map
        """
        acoeff = (self.wavelength / twopi) / (4.0 * self.telescope.focus)
        bcoeff = 4 * self.telescope.focus ** 2
        return acoeff * phase * np.sqrt(self.rad ** 2 + bcoeff)

    def _deviation_to_phase(self, deviation):
        """
        Transforms a physical deviation map to a phase map
        Args:
            deviation: Input physical deviation map

        Returns:
            Phase map
        """
        acoeff = (self.wavelength / twopi) / (4.0 * self.telescope.focus)
        bcoeff = 4 * self.telescope.focus ** 2
        return deviation / (acoeff * np.sqrt(self.rad ** 2 + bcoeff))

    def _build_ring_mask(self):
        """
        Builds the mask on regions to be included in panel surface masks, specific to circular antennas as there is an
        outer and inner limit to the mask based on the antenna's inner receiver hole and outer edge
        """
        self.mask = np.where(self.amplitude < self.cut, False, True)
        self.mask = np.where(self.rad > self.telescope.inlim, self.mask, False)
        self.mask = np.where(self.rad < self.telescope.oulim, self.mask, False)
        self.mask = np.where(np.isnan(self.amplitude), False, self.mask)
        self.mask = np.where(self.deviation != self.deviation, False, self.mask)

    def _build_polar(self):
        """
        Build polar coordinate grid, specific for circular antennas with panels arranged in rings
        """
        u2d = self.u_axis.reshape(self.unpix, 1)
        v2d = self.v_axis.reshape(1, self.vnpix)
        self.rad = np.sqrt(u2d**2 + v2d**2)
        self.phi = np.arctan2(u2d, v2d)
        self.phi = np.where(self.phi < 0, self.phi+twopi, self.phi).T

    def _build_ring_panels(self):
        """
        Build list of panels, specific for circular antennas with panels arranged in rings
        """
        self.panels = []
        for iring in range(self.telescope.nrings):
            angle = 2.0 * np.pi / self.telescope.npanel[iring]
            for ipanel in range(self.telescope.npanel[iring]):
                panel = RingPanel(
                    self.panelkind,
                    angle,
                    ipanel,
                    self._panel_label(iring, ipanel),
                    self.telescope.inrad[iring],
                    self.telescope.ourad[iring],
                    margin=self.panel_margins,
                    screw_scheme=self.telescope.screw_description,
                    screw_offset=self.telescope.screw_offset
                )
                self.panels.append(panel)
        return

    def _compile_panel_points_ringed(self):
        """
        Loops through the points in the antenna surface and checks to which panels it belongs,
        specific for circular antennas with panels arranged in rings
        """
        for ix in range(self.unpix):
            xc = self.u_axis[ix]
            for iy in range(self.vnpix):
                if self.mask[ix, iy]:
                    yc = self.v_axis[iy]
                    for panel in self.panels:
                        issample, inpanel = panel.is_inside(self.rad[ix, iy], self.phi[ix, iy])
                        if inpanel:
                            if issample:
                                panel.add_sample([xc, yc, ix, iy, self.deviation[ix, iy]])
                            else:
                                panel.add_margin([xc, yc, ix, iy, self.deviation[ix, iy]])
                            # A pixel can only belong to one panel, this is a simple optimization
                            break

    def _fetch_panel_ringed(self, ring, panel):
        """
        Fetch a panel object from the panel list using its ring and panel numbers,
        specific for circular antennas with panels arranged in rings
        Args:
            ring: Ring number
            panel: Panel number

        Returns:
        Panel object
        """
        if ring == 1:
            ipanel = panel - 1
        else:
            ipanel = np.sum(self.telescope.npanel[: ring - 1]) + panel - 1
        return self.panels[ipanel]

    def gains(self):
        """
        Computes antenna gains in decibels before and after panel surface fitting
        Returns:
        Gains before panel fitting OR Gains before and after panel fitting
        """
        self.ingains = self._gains_array(self.phase)
        if self.residuals is None:
            return self.ingains
        else:
            self.ougains = self._gains_array(self.phase_residuals)
            return self.ingains, self.ougains

    def _gains_array(self, arr):
        """
        Worker for gains method, works with the actual arrays to compute the gains
        This numpy version is significantly faster than the previous version
        Args:
            arr: Deviation image over which to compute the gains

        Returns:
        Actual and theoretical gains
        """
        thgain = fourpi * (1000.0 * self.reso / self.wavelength) ** 2
        gain = thgain * np.sqrt(np.sum(np.cos(arr[self.mask]))**2 + np.sum(np.sin(arr[self.mask]))**2)/np.sum(self.mask)
        return _convert_to_db(gain), _convert_to_db(thgain)

    def get_rms(self, unit='mm'):
        """
        Computes antenna surface RMS before and after panel surface fitting
        Returns:
        RMS before panel fitting OR RMS before and after panel fitting
        """
        fac = _convert_unit('m', unit, 'length')
        self.in_rms = self._compute_rms_array(self.deviation)
        if self.residuals is None:
            return fac*self.in_rms
        else:
            self.out_rms = self._compute_rms_array(self.residuals)
        return fac*self.in_rms, fac*self.out_rms

    def _compute_rms_array(self, array):
        """
        Factorized the computation of the RMS of an array
        Args:
            array: Input data array

        Returns:
            RMS of the input array
        """
        return np.sqrt(np.mean(array[self.mask] ** 2))

    def fit_surface(self):
        """
        Loops over the panels to fit the panel surfaces
        """
        for panel in self.panels:
            panel.solve()
        self.solved = True

    def correct_surface(self):
        """
        Apply corrections determined by the panel surface fitting methods to the antenna surface
        """
        if not self.solved:
            raise Exception("Panels must be fitted before atempting a correction")
        self.corrections = np.where(self.mask, 0, np.nan)
        self.residuals = np.copy(self.deviation)
        for panel in self.panels:
            corrections = panel.get_corrections()
            for corr in corrections:
                ix, iy = int(corr[0]), int(corr[1])
                self.residuals[ix, iy] -= corr[-1]
                self.corrections[ix, iy] = -corr[-1]
        self.phase_corrections = self._deviation_to_phase(self.corrections)
        self.phase_residuals = self._deviation_to_phase(self.residuals)

    def print_misc(self):
        """
        Print miscelaneous information on the panels in the antenna surface
        """
        for panel in self.panels:
            panel.print_misc()

    def plot_surface(self, filename=None, mask=False, screws=False, dpi=300, plotphase=False, unit=None):
        """
        Do plots of the antenna surface
        Args:
            filename: Save plot to a file rather than displaying it with matplotlib widgets
            mask: Display mask and amplitudes rather than deviation/phase images
            plotphase: plot phase images rather than deviation images
            screws: Display the screws on the panels
            dpi: Plot resolution in DPI
            unit: To do deviation/phase plots, defaults to mm for deviations and degrees for phase
        """

        if mask:
            fig, ax = plt.subplots(1, 2, figsize=[10, 5])
            title = "Mask"
            self._plot_surface(
                self.mask, title, fig, ax[0], 0, 1, screws=screws, mask=mask
            )
            vmin, vmax = np.nanmin(self.amplitude), np.nanmax(self.amplitude)
            title = "Amplitude min={0:.5f}, max ={1:.5f} V".format(vmin, vmax)
            self._plot_surface(
                self.amplitude, title, fig, ax[1], vmin, vmax, screws=screws,
                unit=self.amp_unit,
            )
        else:
            if plotphase:
                if unit is None:
                    unit = 'deg'
                fac = _convert_unit('rad', unit, 'trigonometric')
                self._plot_three_surfaces(self.phase, self.phase_corrections, self.phase_residuals, unit,
                                          fac, screws, 'Antenna surface phase')
            else:
                if unit is None:
                    unit = 'mm'
                fac = _convert_unit('m', unit, 'length')
                self._plot_three_surfaces(self.deviation, self.corrections, self.residuals, unit, fac, screws,
                                          'Antenna surface')
        if filename is None:
            plt.show()
            plt.close()
        else:
            plt.savefig(filename, dpi=dpi)
            plt.close()

    def _plot_three_surfaces(self, original, corrections, residuals, unit, conversion, screws, suptitle):
        """
        Factorizes the plot of the combination of 3 maps
        Args:
            original: Original dataset
            corrections: Corrections applied to the dataset
            residuals: Residuals after correction
            unit: Unit of the output data
            conversion: Conversion factor between internal units and unit
            screws: show screws (Bool)
            suptitle: Superior title to be displayed on top of the figure
        """
        vmax = np.nanmax(np.abs(conversion*original))
        vmin = -vmax
        in_rms = conversion * self._compute_rms_array(original)
        if self.residuals is None:
            fig, ax = plt.subplots()
            title = "Before correction\nRMS = {0:8.5} ".format(in_rms)+unit
            self._plot_surface(conversion * original, title, fig, ax, vmin, vmax, screws=screws, unit=unit)
        else:
            fig, ax = plt.subplots(1, 3, figsize=[15, 5])
            out_rms = conversion * self._compute_rms_array(residuals)
            title = "Before correction\nRMS = {0:.3} ".format(in_rms)+unit
            self._plot_surface(conversion * original, title, fig, ax[0], vmin, vmax, screws=screws, unit=unit)
            title = "Corrections"
            self._plot_surface(conversion * corrections, title, fig, ax[1], vmin, vmax, screws=screws, unit=unit)
            title = "After correction\nRMS = {0:.3} ".format(out_rms)+unit
            self._plot_surface(conversion * residuals, title, fig, ax[2], vmin, vmax, screws=screws, unit=unit)
        fig.suptitle(suptitle)
        fig.tight_layout()

    def _plot_surface(self, data, title, fig, ax, vmin, vmax, screws=False, mask=False, unit="mm"):
        """
        Does the plotting of a data array in a figure's subplot
        Args:
            data: The array to be plotted
            title: Title of the subplot
            fig: Global figure containing the subplots
            ax: matplotlib axes instance describing the subplot
            vmin: minimum to the color scale
            vmax: maximum to the color scale
            screws: Display screws
            mask: do not add colorbar if plotting a mask
            unit: Unit of the data in the color scale
        """
        ax.set_title(title)
        # set the limits of the plot to the limits of the data
        xmin = np.min(self.u_axis)
        xmax = np.max(self.u_axis)
        ymin = np.min(self.v_axis)
        ymax = np.max(self.v_axis)
        im = ax.imshow(
            np.flipud(data),
            cmap="viridis",
            interpolation="nearest",
            extent=[xmin, xmax, ymin, ymax],
            vmin=vmin,
            vmax=vmax,
        )
        divider = make_axes_locatable(ax)
        if not mask:
            cax = divider.append_axes("right", size="5%", pad=0.05)
            fig.colorbar(im, label="Z Scale [" + unit + "]", cax=cax)
        ax.set_xlabel("X axis [m]")
        ax.set_ylabel("Y axis [m]")
        for panel in self.panels:
            panel.plot(ax, screws=screws)

    def _build_panel_data_arrays(self):
        """
        Build arrays with data from the panels so that they can be stored on the XDS
        Returns:
            List with panel labels, panel fitting parameters, screw_adjustments
        """
        npanels = len(self.panels)
        NPAR = self.panels[0].NPAR
        nscrews = self.panels[0].screws.shape[0]
        panel_labels = np.ndarray([npanels], dtype=object)
        panel_pars = np.ndarray((npanels, NPAR), dtype=float)
        screw_adjustments = np.ndarray((npanels, nscrews), dtype=float)
        for ipanel in range(npanels):
            panel_labels[ipanel] = self.panels[ipanel].label
            panel_pars[ipanel, :] = self.panels[ipanel].par
            screw_adjustments[ipanel, :] = self.panels[ipanel].export_screws_float(unit='m')
        return panel_labels, panel_pars, screw_adjustments

    def export_screw_adjustments(self, filename, unit="mm"):
        """
        Export screw adjustments for all panels onto an ASCII file
        Args:
            filename: ASCII file name/path
            unit: unit for panel screw adjustments ['mm','miliinches']
        """
        spc = " "
        outfile = "Screw adjustments for {0:s} {1:s} antenna\n".format(
            self.telescope.name, self.antenna_name
        )
        outfile += "Adjustments are in " + unit + lnbr
        outfile += 2 * lnbr
        outfile += 25 * spc + "{0:22s}{1:22s}".format("Inner Edge", "Outer Edge") + lnbr
        outfile += 5 * spc + "{0:8s}{1:8s}".format("Ring", "panel")
        outfile += 2 * spc + 2 * "{0:11s}{1:11s}".format("left", "right") + lnbr
        for panel in self.panels:
            outfile += panel.export_adjustments(unit=unit) + lnbr
        lefile = open(filename, "w")
        lefile.write(outfile)
        lefile.close()

    def export_xds(self):
        """
        Export all the data to Xarray dataset
        Returns:
            XarrayDataSet contaning all the relevant information
        """
        xds = xr.Dataset()
        gains = self.gains()
        rms = self.get_rms(unit='m')
        xds.attrs['telescope_name'] = self.telescope.name
        xds.attrs['antenna_name'] = self.antenna_name
        xds.attrs['wavelength'] = self.wavelength
        xds.attrs['AIPS'] = False
        xds.attrs['amp_unit'] = self.amp_unit
        xds.attrs['panel_kind'] = self.panelkind
        xds.attrs['panel_margin'] = self.panel_margins
        xds.attrs['cutoff'] = self.cut
        xds['AMPLITUDE'] = xr.DataArray(self.amplitude, dims=["u", "v"])
        xds['PHASE'] = xr.DataArray(self.phase, dims=["u", "v"])
        xds['DEVIATION'] = xr.DataArray(self.deviation, dims=["u", "v"])
        xds['MASK'] = xr.DataArray(self.mask, dims=["u", "v"])
        if self.residuals is not None:
            xds['PHASE_RESIDUALS'] = xr.DataArray(self.phase_residuals, dims=["u", "v"])
            xds['RESIDUALS'] = xr.DataArray(self.residuals, dims=["u", "v"])
            xds['PHASE_CORRECTIONS'] = xr.DataArray(self.phase_corrections, dims=["u", "v"])
            xds['CORRECTIONS'] = xr.DataArray(self.corrections, dims=["u", "v"])
            xds.attrs['input_rms'] = rms[0]
            xds.attrs['output_rms'] = rms[1]
            xds.attrs['input_gain'] = gains[0][0]
            xds.attrs['output_gain'] = gains[1][0]
            xds.attrs['theoretical_gain'] = gains[0][1]
        else:
            xds.attrs['input_rms'] = rms
            xds.attrs['input_gain'] = gains[0]
            xds.attrs['theoretical_gain'] = gains[1]

        if self.solved:
            labels, pars, screws = self._build_panel_data_arrays()
            xds['PANEL_PARAMETERS'] = xr.DataArray(pars, dims=['labels', 'pars'])
            xds['PANEL_SCREWS'] = xr.DataArray(screws, dims=['labels', 'screws'])
            coords = {"u": self.u_axis, "v": self.v_axis, 'labels': labels, 'screws': self.telescope.screw_description,
                      'pars': np.arange(pars.shape[1])}
        else:
            coords = {"u": self.u_axis, "v": self.v_axis}

        xds = xds.assign_coords(coords)
        return xds
