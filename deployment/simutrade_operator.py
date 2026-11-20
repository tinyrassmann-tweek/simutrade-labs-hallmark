"""Run the existing owner's fulfillment actions without printing credentials."""
import argparse
import base64
import json
import pathlib
import shutil
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('activate', 'suspend', 'team'))
    parser.add_argument('record', help='Private JSON file, or the team ID for a read')
    args = parser.parse_args()
    gcloud = shutil.which('gcloud')
    if not gcloud:
        installed = pathlib.Path.home() / 'google-cloud-sdk' / 'bin' / 'gcloud'
        if installed.is_file():
            gcloud = str(installed)
    if not gcloud:
        raise SystemExit('The existing Google Cloud CLI installation was not found.')
    token = subprocess.check_output(
        [gcloud, 'auth', 'print-identity-token'], text=True,
        stderr=subprocess.DEVNULL).strip()
    claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
    if claims.get('email', '').lower() != 'tiny.rassmann@gmail.com':
        raise SystemExit('Use the existing owner Google Cloud sign-in.')
    context = ssl.create_default_context()
    if not context.cert_store_stats()['x509_ca']:
        bundle = (pathlib.Path(gcloud).resolve().parents[1] / 'lib' /
                  'third_party' / 'certifi' / 'cacert.pem')
        if not bundle.is_file():
            raise SystemExit('Restore the existing official Google Cloud CA bundle.')
        context = ssl.create_default_context(cafile=str(bundle))
    url = ('https://simutradelabs.thinktanksolutionsai.online/'
           'api/simutrade/operator/' + args.action)
    body = None
    if args.action == 'team':
        url += '?' + urllib.parse.urlencode({'id': args.record})
    else:
        body = json.dumps(json.loads(pathlib.Path(args.record).read_text())).encode()
    request = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(request, timeout=45, context=context) as response:
            print(json.dumps(json.load(response), indent=2))
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get('error', 'Operator request rejected.')
        except (ValueError, AttributeError):
            message = 'Operator request rejected.'
        raise SystemExit('HTTP ' + str(error.code) + ': ' + str(message)) from None


if __name__ == '__main__':
    main()
