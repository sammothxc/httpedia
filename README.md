![HTTPedia Logo](/static/httpedia-logo.gif)

**A lightweight Wikipedia proxy for vintage computers and retro web browsers.**

Modern Wikipedia is filled JavaScript, complex CSS, high-resolution images, and it makes use of lots of modern browser features that old machines can't handle.
HTTPedia strips all that away and serves clean HTML 3.2 that works on browsers from the 1990s and earlier.
In addition to cutting down on complexity, HTTPedia is served over HTTP meaning there are no minimum HTTPS or TLS requirements.

🌐 **Check it out:** [http://httpedia.samwarr.net](http://httpedia.samwarr.net)


## Features

- No HTTPS required! Works on machines that can't handle modern TLS
- Pure, <a href="https://validator.w3.org/check?uri=http%3A%2F%2Fhttpedia.samwarr.net%2F">
validated HTML 3.2 output</a> (no JavaScript or CSS)<br>
- All images converted to GIFs for compatibility<br>
- Light and dark modes<br>
- Option to load one, all, or disable images entirely<br>
- Works on Netscape, Mosaic, early IE, text browsers, even Microweb on an 8088!
- [COMING SOON] Support for multiple languages


## Compatibility

Tested and working on:

- Netscape Navigator 2.0+
- Mosaic
- Internet Explorer 3.0+
- Lynx and other text browsers
- Microweb on an 8088 PC clone
- Basically anything that can render HTML


## How It Works

1. User requests an article
2. HTTPedia fetches the page from Wikipedia
3. HTML is parsed and stripped down to essential content
4. Images are fetched and converted to GIF
5. Pure HTML 3.2 is returned to the user

All processing happens server-side, so the client just receives simple, lightweight HTML.


## Rate Limits

To protect both the server and Wikipedia's API:

- General requests: 1 per second per IP
- Image requests: 5 per second per IP


## Contributing

Found a bug? Have a feature request? Want to improve compatibility with an obscure browser?

[Open an issue](https://github.com/sammothxc/httpedia/issues) or submit a pull request!


## Support

If HTTPedia felt like a blast from the past on your vintage hardware, consider supporting the project and others like it :<zero-width space>)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/V7V81SAPLN)

Donations go toward server hosting costs, and hopefully more projects like this one.


## License

GNU General Public License v3.0, see [LICENSE](LICENSE) for details.


## Acknowledgments

- Content sourced from [Wikipedia](https://www.wikipedia.org/) under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Inspired by [FrogFind](http://frogfind.com) and [68k.news](http://68k.news), go check them out!

---


*Because old computers deserve to access information too.*
