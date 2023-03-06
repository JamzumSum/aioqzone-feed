# aioqzone-feed

An [aioqzone][aioqzone] plugin for handling feeds, a high-level api for feed operation.

[![python](https://img.shields.io/badge/python-3.8%20%7C%203.11-blue)][home]
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Feature

- [x] Fetch feeds easily
- [x] Optimize for `311` feeds
- [x] Lazy update for raw photos and videos
- [x] Inner heartbeat management
- [x] Qzone emoji translate ([QzEmoji][qzemoji])
- [x] All in async
- [x] aioqzone hook support
- [ ] Unit test 🆘

## Usage

See our [doucument][doc].

## License

- [AGPL-3.0](LICENSE)
- `aioqzone-feed` is a plugin of [aioqzone][aioqzone]. This repository inherits license, instructions and any disclaimers from `aioqzone`. See also: [License fragment in aioqzone README file](https://github.com/aioqzone/aioqzone#license)


[aioqzone]: https://github.com/aioqzone/aioqzone "Python wrapper for Qzone web login and Qzone http api."
[qzemoji]: https://github.com/aioqzone/QzEmoji/tree/async "Translate Qzone emoji to text"
[doc]: https://aioqzone.github.io/aioqzone-feed "Documentation for aioqzone-feed"
[home]: https://github.com/aioqzone/aioqzone-feed "aioqzone plugin providing higher level api for processing feed"
