# plotting-service
The plotting service provides a [h5-grove](https://github.com/silx-kit/h5grove) fastapi implementation    
![License: GPL-3.0](https://img.shields.io/github/license/fiaisis/run-detection)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/PyCQA/pylint)

## Local Install
`pip install .[all]`
You may need to escape the square brackets e.g. \[all\]


## Running Directly for development

The `CEPH_DIR` environment variable must be set, else it will default to `/ceph`

It is assumed that the directory structure for reduced data is as follows:  
`<CEPH_DIR>/<instrument>/RBNumber/RB<RBNUMBER>/autoreduced/<NEXUS FILE>`
E.g  `/ceph/mari/RBNumber/RB12345/autoreduced/MAR_1231231.nxspe`

```shell
uvicorn plotting_service.plotting_api:app --reload  
```

The reload option will reload the api on code changes.
