# Third-Party Notices

Momind is licensed under the MIT License. That license applies to the original
Momind source code and does not replace the licenses, notices, trademarks, or
service terms of the third-party components listed below.

The authoritative license distributed with each dependency controls if this
summary differs from it. Versions are pinned in `req.txt` or specified in the
HTML template CDN URL unless noted otherwise.

## AI services and models

| Component | Use in Momind | License or terms |
| --- | --- | --- |
| [Groq Python SDK](https://github.com/groq/groq-python) | Connects server-side AI features to the Groq API | Apache License 2.0 |
| [GroqCloud](https://console.groq.com/docs/legal) | Hosted inference service; not distributed with Momind | GroqCloud terms, privacy terms, acceptable-use policy, and provider documentation |
| `openai/gpt-oss-120b` | Default model identifier configured for Groq-hosted explanations | Model-specific terms published by the model provider and the Groq service terms |
| [XGBoost](https://github.com/dmlc/xgboost) | Optional maternal-risk scoring model runtime | Apache License 2.0 |

API access does not grant rights to provider names or trademarks. Deployers
must supply their own credentials and confirm that the selected hosted model,
input data, location, and use case comply with the applicable provider terms.

## Python runtime dependencies

| Packages | License |
| --- | --- |
| [Django](https://github.com/django/django), [asgiref](https://github.com/django/asgiref), [sqlparse](https://github.com/andialbrecht/sqlparse) | BSD 3-Clause |
| [groq](https://github.com/groq/groq-python), [distro](https://github.com/python-distro/distro) | Apache License 2.0 |
| [xgboost](https://github.com/dmlc/xgboost) | Apache License 2.0 |
| [NumPy](https://github.com/numpy/numpy), [pandas](https://github.com/pandas-dev/pandas), [SciPy](https://github.com/scipy/scipy) | BSD 3-Clause; binary distributions may include separately licensed bundled libraries described in their distributions |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD 3-Clause |
| [Pydantic](https://github.com/pydantic/pydantic), [pydantic-core](https://github.com/pydantic/pydantic-core), [annotated-types](https://github.com/annotated-types/annotated-types), [typing-inspection](https://github.com/pydantic/typing-inspection) | MIT |
| [HTTPX](https://github.com/encode/httpx), [HTTPCore](https://github.com/encode/httpcore), [idna](https://github.com/kjd/idna) | BSD 3-Clause |
| [AnyIO](https://github.com/agronholm/anyio), [h11](https://github.com/python-hyper/h11), [six](https://github.com/benjaminp/six) | MIT |
| [sniffio](https://github.com/python-trio/sniffio) | MIT OR Apache License 2.0 |
| [certifi](https://github.com/certifi/python-certifi) | Mozilla Public License 2.0 |
| [python-dateutil](https://github.com/dateutil/dateutil) | Apache License 2.0 OR BSD 3-Clause |
| [typing_extensions](https://github.com/python/typing_extensions) | Python Software Foundation License 2.0 |
| [NVIDIA NCCL Python package](https://docs.nvidia.com/deeplearning/nccl/) (`nvidia-nccl-cu12`) | NVIDIA NCCL Software License Agreement; verify redistribution rights before packaging or redistributing its binaries |

The installed distributions may contain their full license texts in package
metadata. Distributors of bundled builds should retain those files and all
required copyright and attribution notices.

## Browser libraries, icons, and fonts

These assets are loaded from external CDNs by Momind templates. CDN delivery
does not change the underlying project's license.

| Component | Version used | License |
| --- | --- | --- |
| [Bootstrap](https://github.com/twbs/bootstrap) | 5.3.0 | MIT |
| [Bootstrap Icons](https://github.com/twbs/icons) | 1.11.3 | MIT |
| [Font Awesome Free](https://fontawesome.com/license/free) | 6.0.0 beta 3 and 6.5.1 | Icons: CC BY 4.0; fonts: SIL OFL 1.1; code: MIT |
| [FullCalendar](https://github.com/fullcalendar/fullcalendar) | 6.1.15 standard/global build | MIT; premium plugins have separate commercial terms and are not intentionally included |
| [Chart.js](https://github.com/chartjs/Chart.js) | CDN-selected version (currently unpinned) | MIT |
| [Marked](https://github.com/markedjs/marked) | CDN-selected version (currently unpinned) | MIT |
| [QRCode.js](https://github.com/davidshimjs/qrcodejs) | 1.0.0 | MIT |
| [html5-qrcode](https://github.com/mebjas/html5-qrcode) | 2.3.8 | Apache License 2.0 |
| [Inter](https://github.com/rsms/inter) | Google Fonts hosted | SIL Open Font License 1.1 |
| [Fraunces](https://github.com/undercasetype/Fraunces) | Google Fonts hosted | SIL Open Font License 1.1 |

The project currently uses jsDelivr, cdnjs, and Google Fonts to deliver some
assets at runtime. Their respective service terms and privacy practices also
apply to requests made by a user's browser.

## Uploaded and user-provided material

Files under attachment, upload, media, or generated-data directories are not
automatically licensed under Momind's MIT License. Each file remains subject to
its owner's copyright, privacy rights, consent, and any applicable source
license. Do not redistribute reports, images, documents, datasets, or generated
content unless the project has documented permission to do so.

## Trademarks and medical use

Third-party names and logos remain the property of their respective owners and
are used only to identify dependencies. The open-source licenses above do not
certify Momind as a medical device or authorize clinical deployment. Any such
deployment requires separate safety, privacy, regulatory, and professional
review.
