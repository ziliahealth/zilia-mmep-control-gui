import numpy as np
import matplotlib.pyplot as plt


class HemoglobinDissociationDash2010:
    """
    A Python class to model blood HbO2 dissociation curves based on a corrected
    implementation of the Dash et al. 2010 errata reprint (JSim Model 0149).

    The model is initialized with a baseline physiological state (pH, pCO2, etc.),
    and the calculate_sO2 method can then be called for different temperatures.
    """

    def __init__(self, pH: float = 7.24, pCO2: float = 40.0,
                 DPG: float = 4.65e-3, Hct: float = 0.45):
        """
        Initializes the model with a specific set of steady-state physiological parameters.
        Temperature is excluded here and passed to the calculation method.
        """
        # --- Store input parameters ---
        self.pH = pH
        self.pCO2 = pCO2
        self.DPG = DPG
        self.Hct = Hct

        # --- Fixed model constants ---
        self.Wpl = 0.94
        self.Wrbc = 0.65
        self.K2dp = 1.0e-6
        self.K2p = 2.95e-5 / self.K2dp
        self.K3dp = 1.0e-6
        self.K3p = 2.51e-5 / self.K3dp
        self.K5dp = 2.63e-8
        self.K6dp = 1.91e-8
        self.nhill = 2.7
        self.n0 = self.nhill - 1.0

        # --- Standard physiological values ---
        self.pO20 = 100.0
        self.pCO20 = 40.0
        self.pH0 = 7.24
        self.DPG0 = 4.65e-3
        self.Temp0 = 37.0
        self.P500 = 26.8

        # --- Derived standard constants ---
        self.fact = 1.0e-6 / self.Wpl
        self.alphaO20 = self.fact * 1.37
        self.alphaCO20 = self.fact * 30.7
        self.O20 = self.alphaO20 * self.pO20
        self.CO20 = self.alphaCO20 * self.pCO20
        self.Hp0 = 10 ** (-self.pH0)
        self.C500 = self.alphaO20 * self.P500

    def calculate_sO2(self, pO2_values, temperature: float) -> np.ndarray:
        """
        Calculates sO2 for an array of pO2 values at a specific temperature.

        Args:
            pO2_values (np.ndarray): An array of O2 partial pressures in mmHg.
            temperature (float): The blood temperature in degrees Celsius for this calculation.

        Returns:
            np.ndarray: A corresponding array of sO2 values (unitless fraction).
        """
        # --- Calculate intermediate variables ---
        pHdiff = self.pH - self.pH0
        pCO2diff = self.pCO2 - self.pCO20
        DPGdiff = self.DPG - self.DPG0
        Tempdiff = temperature - self.Temp0

        alphaO2 = self.fact * (1.37 - 0.0137 * Tempdiff + 0.00058 * Tempdiff ** 2)
        alphaCO2 = self.fact * (30.7 - 0.57 * Tempdiff + 0.02 * Tempdiff ** 2)

        O2 = alphaO2 * pO2_values
        CO2 = alphaCO2 * self.pCO2
        Hp = 10 ** (-self.pH)

        Term1 = self.K2p * (1 + self.K2dp / Hp)
        Term2 = self.K3p * (1 + self.K3dp / Hp)
        Term3 = (1 + Hp / self.K5dp)
        Term4 = (1 + Hp / self.K6dp)
        Term10 = self.K2p * (1 + self.K2dp / self.Hp0)
        Term20 = self.K3p * (1 + self.K3dp / self.Hp0)
        Term30 = (1 + self.Hp0 / self.K5dp)
        Term40 = (1 + self.Hp0 / self.K6dp)

        Kratio10 = (Term10 * self.CO20 + Term30) / (Term20 * self.CO20 + Term40)
        Kratio11 = (Term1 * self.CO20 + Term3) / (Term2 * self.CO20 + Term4)
        Kratio12 = (Term10 * self.alphaCO20 * self.pCO2 + Term30) / \
                   (Term20 * self.alphaCO20 * self.pCO2 + Term40)

        K4dp = Kratio10 * ((self.O20) ** self.n0 / (self.C500) ** self.nhill)
        K4tp = K4dp / (self.O20) ** self.n0

        Kratio20 = Kratio10 / K4tp
        Kratio21 = Kratio11 / K4tp
        Kratio22 = Kratio12 / K4tp

        P501 = 26.765 - 21.279 * pHdiff + 8.872 * pHdiff ** 2
        P502 = 26.80 + 0.0428 * pCO2diff + 3.64e-5 * pCO2diff ** 2
        P503 = 26.78 + 795.633533 * DPGdiff - 19660.8947 * DPGdiff ** 2
        P504 = 26.75 + 1.4945 * Tempdiff + 0.04335 * Tempdiff ** 2 + 0.0007 * Tempdiff ** 3

        C501 = self.alphaO20 * P501
        C502 = self.alphaO20 * P502
        C503 = self.alphaO20 * P503
        C504 = alphaO2 * P504

        if abs(pHdiff) < 1e-9:
            n1 = 1.0
        else:
            n1 = (np.log(Kratio21) - self.nhill * np.log(C501)) / (pHdiff * np.log(10))

        n2 = 1.0 if abs(pCO2diff) < 1e-9 else (np.log(Kratio22) - self.nhill * np.log(C502)) / (
                    np.log(self.CO20) - np.log(CO2))
        n3 = 1.0 if abs(DPGdiff) < 1e-9 else (np.log(Kratio20) - self.nhill * np.log(C503)) / (
                    np.log(self.DPG0) - np.log(self.DPG))
        n4 = 1.0 if abs(Tempdiff) < 1e-9 else (np.log(Kratio20) - self.nhill * np.log(C504)) / (
                    np.log(self.Temp0 + 273.15) - np.log(temperature + 273.15))

        Term5 = (self.Hp0 / Hp) ** n1 * (self.CO20 / CO2) ** n2 * \
                (self.DPG0 / self.DPG) ** n3 * ((self.Temp0 + 273.15) / (temperature + 273.15)) ** n4

        K4p = K4dp * (O2 / self.O20) ** self.n0 * Term5
        KHbO2 = K4p * (Term2 * CO2 + Term4) / (Term1 * CO2 + Term3)
        sO2 = KHbO2 * O2 / (1 + KHbO2 * O2)

        return sO2

    def test(self, jsim_data_path: str, temperature: float, plot: bool = True):
        """
        Validates the current model instance against a JSim data file by plotting both curves.

        This method assumes the model has been initialized with parameters (pH, pCO2, etc.)
        that match the conditions used to generate the JSim reference file. The test is
        run at a fixed temperature of 37.0°C, which is standard for these data sets.

        Args:
            jsim_data_path (str): The full path to the JSim reference CSV file.
            plot (bool): If True, a comparison plot will be displayed.
        """
        print("--- Running Validation Test ---")
        print(f"Testing model state: pH={self.pH}, pCO2={self.pCO2}, DPG={self.DPG}, Hct={self.Hct}")

        # The validation data is typically generated at a standard temperature
        test_temperature = temperature

        # Generate pO2 range and calculate the sO2 curve using the model's state
        po2_range = np.arange(0.5, 100.5, 0.5)
        sO2_python = self.calculate_sO2(po2_range, temperature=test_temperature)

        # Load the reference data from the JSim model CSV file
        try:
            jsim_data = np.loadtxt(jsim_data_path, delimiter=',', skiprows=2, usecols=[1, 2])
            print(f"Successfully loaded JSim data from: {jsim_data_path}")
        except FileNotFoundError:
            print(f"Error: Could not find the JSim data file at '{jsim_data_path}'.")
            return

        #compute the RMSE between the two curves
        if jsim_data.shape[0] != sO2_python.shape[0]:
            print("Error: The JSim data and Python model data have different lengths.")
            return
        rmse = np.sqrt(np.mean((jsim_data[:, 1] - sO2_python) ** 2))
        if rmse <=0.001:
            test_result = "PASS"
        else:
            test_result = "FAIL"

        print(f"Test Result: {test_result} (RMSE = {rmse:.4f})")

        if plot:
            plt.figure(figsize=(12, 8))
            plt.plot(po2_range, sO2_python, label='Python Implementation', color='blue', linewidth=2.5)
            plt.plot(jsim_data[:, 0], jsim_data[:, 1], label='Data from JSIM model', color='red', linestyle='--',
                     linewidth=2)
            plt.title(f'Validation : Python vs JSIM \n'
                      f'Temp = {test_temperature}C, pH = {self.pH}, pCO2 = {self.pCO2} mmHg, ', fontsize=16)
            plt.xlabel('pO₂ (mmHg)', fontsize=12)
            plt.ylabel('Hemoglobin O₂ Saturation', fontsize=12)
            plt.legend(fontsize=11)
            plt.grid(True, linestyle=':', alpha=0.6)
            plt.text(5, 0.1, f'RMSE: {rmse:.4f}', fontsize=12, color='black',
                     bbox=dict(facecolor='white', alpha=0.8, edgecolor='black'))
            plt.xlim(0, 100)
            plt.ylim(0, 1)
            plt.show()

if __name__ == "__main__":
    # Example usage and test
    model = HemoglobinDissociationDash2010(pH=7.56, pCO2=40.0, DPG=4.65e-3, Hct=0.45)
    test_file = r'DO Sensor Calibration/dash2010_jsim_37TEMP_7.56PH_40PCO2_0.45HCT_0.00465DPG.csv'
    model.test(jsim_data_path=test_file, temperature=37, plot=True)
    model = HemoglobinDissociationDash2010(pH=7.35, pCO2=35, DPG=4.65e-3, Hct=0.45)
    test_file = r'DO Sensor Calibration/dash2010_jsim_35TEMP_7.35PH_35PCO2_0.45HCT_0.00465DPG.csv'
    model.test(jsim_data_path=test_file, temperature=35, plot=True)
    print(model.calculate_sO2(50, temperature=37))