from setuptools import setup, find_packages
from os import path


here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name="streamdeckd",
    version="1.0.0",
    description="StreamDeck Daemon",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    author = "stuxcrystal",
    packages=find_packages(),

    install_requires=["streamdeck", "crossplane", "aiorun", "pillow"],
    extras_require={
        "all": ["aiohttp", "jsonpath-ng", "pulsectl"],
        "http": ["aiohttp", "jsonpath-ng"],
        "pulseaudio": ["pulsectl"]
    },

    include_package_data=True,
    entry_points = {
        'console_scripts': [
            "streamdeckd=streamdeckd.__main__:main"
        ]
    },
    project_urls={}
) 