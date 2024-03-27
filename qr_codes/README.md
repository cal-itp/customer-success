# Generate QR codes

> Generate a QR code as an PNG file

1. Open this repository's devcontainer in VS Code
2. Change into the `qr_codes` directory
3. Run the helper script

```bash
$ python main.py -h
usage: main.py [-h] [--color COLOR] [--background BACKGROUND] [--size SIZE] data output

Generate a QR code as an PNG file

positional arguments:
  data                  The data to encode as a QR code
  output                Path to an PNG file where the QR code is written

options:
  -h, --help            show this help message and exit
  --color COLOR         The color of the QR code in hex format, by default black
  --background BACKGROUND
                        The background color of the QR code in hex format, by default transparent
  --size SIZE           The QR code size from 1-10, by default 4
```
