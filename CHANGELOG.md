## 0.4.3 (2024-10-11)



### Bug Fixes
* Enable close button  on the submitter dialog in Blender 4.2 (#127) ([`c9582ea`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/c9582eaa46fa09b9829b3bae2ec390436bf022b7))
* Use python-use-system-env to have Blender check PYTHONPATH. (#125) ([`c73bbe2`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/c73bbe2058fb2e61e80d8577164bc229790a6e0d))

## 0.4.2 (2024-09-03)



### Bug Fixes
* correct adaptor override developer option (#117) ([`b8be198`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/b8be1989dfd745cfc04adde35a70b836da0591b5))

## 0.4.1 (2024-05-01)

### Dependencies
* Update deadline requirement from ==0.47.* to ==0.48.* (#100) ([`d41cb26`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/d41cb26a5f0495ae2666cb50701494f6da9c8430))


## 0.4.0 (2024-04-17)

### BREAKING CHANGES
* exclude view layers if not used for rendering (#92) ([`fe29282`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/fe29282bb5fe041ff0a9508054ebfaa0410b0aad))
* set frame override and remove job_settings.py (#91) ([`7a350bb`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/7a350bbb60c8340a235ba5fbbd1268df800428c1))


### Bug Fixes
* override frame range checkbox (#90) ([`a900d7c`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/a900d7cff01ef51510f16f427416026a8b431ec8))

## 0.3.0 (2024-04-01)

### BREAKING CHANGES
* public release (#80) ([`e5af3b7`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/e5af3b71f90b80f2b932220ffe6a1ce044542528))


### Bug Fixes
* Prevents the submission dialog from locking Blender on Linux (#81) ([`7730b11`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/7730b11cf32e0de9756e5c16ee4c349a96e62774))
* include the adaptor deps in the package (#79) ([`fe6f0af`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/fe6f0af9726d10e1bac4c9ad3d3f8500be249e61))
* incorrect package name in create adaptor script (#78) ([`7b92e91`](https://github.com/aws-deadline/deadline-cloud-for-blender/commit/7b92e91fa1edc6c2974f80971afe93194d745797))

## 0.2.2 (2024-03-26)


### Features
* swap to qtpy (#75) ([`b5c0c3a`](https://github.com/casillas2/deadline-cloud-for-blender/commit/b5c0c3ad09729b63a0431f07a9c2ffa68b7f27f3))
* Adds telemetry events to submitter and adaptor (#63) ([`8f0fb2d`](https://github.com/casillas2/deadline-cloud-for-blender/commit/8f0fb2d85f2c9054eaceb384df1cd4711ec76ed6))

### Bug Fixes
* include the adaptor deps in the package (#74) ([`ae09907`](https://github.com/casillas2/deadline-cloud-for-blender/commit/ae0990753d0f31dbf8cfd4805191b44661458c9e))
* include deadline-cloud in the adaptor packaging script (#73) ([`9de3146`](https://github.com/casillas2/deadline-cloud-for-blender/commit/9de31469a1485901d40a0993cbee36838c8774fa))

## 0.2.1 (2024-03-15)

### Chores
* update deps deadline-cloud 0.40 (#60) ([`cebd1c4`](https://github.com/casillas2/deadline-cloud-for-blender/commit/ced54bfef7bfbcc9743e0f2660942528b326fb6a))

## 0.2.0 (2024-03-08)

### BREAKING CHANGES
* updated openjd-runtime to 0.5.* (#54) ([`3fcc0e8`](https://github.com/casillas2/deadline-cloud-for-blender/commit/3fcc0e8dff8790cb856b8e3e1c86cdeffc6bffea))


### Bug Fixes
* remove variables from bl_info (#53) ([`4d0cda6`](https://github.com/casillas2/deadline-cloud-for-blender/commit/4d0cda637d6f66604c86f341ab33d605e70ecdf3))
* adaptor client changes for windows (#47) ([`b69a0df`](https://github.com/casillas2/deadline-cloud-for-blender/commit/b69a0df940e5eab6631079dbb271e8b18aba4d1f))


## v0.1.1 (2024-02-22)

### Fix
* fix: create module dir if it doesn&#39;t exist in installation (#43)


## v0.1.0 (2024-02-21)

### Breaking
* feat!: initial new blender integration (#37)
