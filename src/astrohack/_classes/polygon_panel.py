from shapely import Polygon
from shapely.plotting import plot_polygon
from astrohack._classes.base_panel import BasePanel, panelkinds, icorpara


class GeneralPanel(BasePanel):

    def __init__(self, kind, ipanel, polygon, screws):
        """
        Initializes a polygon based panel based on a polygon shape and the screw positions
        Args:
            kind: What kind of surface to be used in fitting ["rigid", "mean", "xyparaboloid", "rotatedparaboloid"]
            ipanel: Panel number
            polygon: Polygon describing the panel shape
            screws: Positions of the screw over the panel
        """
        super().__init__(kind, ipanel, screws)
        self.polygon = Polygon(polygon)
        self.center = self.polygon.centroid
        if kind == panelkinds[icorpara]:
            raise Exception('corotatedparaboloid not supported for Polygon based panels')
        return

    def is_inside(self, point):
        """
        Checks if a point is inside the panel by using shapely's point in polygon method
        Args:
            point: point to be tested
        """
        return self.polygon.within(point)

    def export_adjustments(self, unit='mm'):
        """
        Exports panel screw adjustments to a string
        Args:
            unit: Unit for screw adjustments ['mm','miliinches']

        Returns:
        String with screw adjustments for this panel
        """
        string = '{0:8d}'.format(self.ipanel)
        return string+self.export_screw_adjustments(unit)

    def print_misc(self, verbose=False):
        """
        Print miscelaneous information about the panel to the terminal
        Args:
            verbose: Include more information in print
        """
        print("########################################")
        print("{0:20s}={1:8d}".format("ipanel", self.ipanel))
        print("{0:20s}={1:8s}".format("kind", " " + self.kind))
        print("{0:20s}={1:8d}".format("nsamp", self.nsamp))
        if verbose:
            for isamp in range(self.nsamp):
                strg = "{0:20s}=".format("samp{0:d}".format(isamp))
                for val in self.values[isamp]:
                    strg += str(val) + ", "
                print(strg)
        print()

    def plot(self, ax, screws=False):
        """
        Plot panel outline to ax
        Args:
            ax: matplotlib axes instance
            screws: Display screws in plot
        """
        plot_polygon(self.polygon, ax=ax, add_points=False, color=self.linecolor, linewidth=self.linewidth)
        self.plot_label(ax)
        if screws:
            self.plot_screws(ax)
        return
