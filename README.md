## DEFA Power EV Charger Home Assistant Integration

This is a custom integration for Home Assistant that allows you to control and monitor your DEFA Power EV charger using the **CloudCharge API**, similar to the official DEFA Power app.

### Features

- Communicate with your DEFA Power EV charger via the CloudCharge API.
- Monitor charging status and other key metrics.
- Start and stop charging.
- Restart the charger.

### Installation Instructions

#### HACS (Home Assistant Community Store)

1. Ensure that you have [HACS](https://hacs.xyz/) installed in your Home Assistant setup.
2. Go to HACS in the Home Assistant sidebar.
3. Click on the three dots in the top right corner and select "Custom repositories".
4. Add the repository URL `https://github.com/Bebbssos/ha-defa-power` and set the type to "Integration".
5. Find "DEFA Power" in the list of integrations and click "Download".
6. Restart Home Assistant.

#### Manual Installation

1. Clone this repository or download the ZIP file.
2. Copy the `custom_components/defa_power` directory to your Home Assistant `config/custom_components` directory.
3. Restart Home Assistant.

### Setup Instructions

1. In Home Assistant, go to `Configuration` > `Integrations`.
2. Click on the `+ Add Integration` button in the bottom right corner.
3. Search for `DEFA Power` and select it.
4. Follow the on-screen instructions to complete the setup.

#### Configuration Options

You will be prompted to choose a login method:

- **Phone Number Login**: Use your phone number to receive an SMS code.
- **Manual Login**: Enter your user-id and token manually.

##### Phone Number Login

1. Enter your phone number in the international format (e.g., +1234567890).
2. Select an app to simulate:

   - **Cloud Charge**: Simulate the Cloud Charge app.
   - **DEFA Power**: Simulate the DEFA Power app.
   - **Custom Developer Token**: Enter a custom developer token.

   **Why is this needed?**
   The CloudCharge API allows only one active session per app at a time. By selecting an app to simulate, you can avoid conflicts with the app you are currently using on your phone. Choose an app that you are not actively using to avoid being logged out. The API identifies the app by the `devToken` sent in the login request.

3. If you selected "Custom Developer Token", enter your custom token in the `Custom developer token` field.
4. You will receive an SMS code on your phone. Enter this code in the next step to complete the login.

##### Manual Login

If you already have your user-id and a valid token, you can enter them manually here.

### Retrieving User-ID and Token

After setting up the integration, you can retrieve your user-id and token by following these steps:

1. Go to the DEFA Power integration in Home Assistant.
2. Select `Configure` on the integration instance.
3. Choose `Show current token`.

### To-Do List

- [ ] **Additional Entities**: Add more entities from the data provided by the CloudCharge API.
- [ ] **Eco Mode Configuration**: Add functionality to set eco mode options.

### Disclaimer

- _This project is not affiliated with, endorsed, or supported by DEFA AS._
