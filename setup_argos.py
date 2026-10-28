"""Install the official Argos English -> Vietnamese package once."""
from translation_service import translate_vi
import argostranslate.package


def main():
    installed = argostranslate.package.get_installed_packages()
    if not any(p.from_code == 'en' and p.to_code == 'vi' for p in installed):
        print('Downloading Argos English -> Vietnamese model...', flush=True)
        argostranslate.package.update_package_index()
        package = next((p for p in argostranslate.package.get_available_packages()
                        if p.from_code == 'en' and p.to_code == 'vi'), None)
        if package is None:
            raise RuntimeError('No English -> Vietnamese package in the official Argos index.')
        argostranslate.package.install_from_path(package.download())
    print('Argos ready: bottle -> ' + translate_vi('bottle'), flush=True)


if __name__ == '__main__':
    main()
