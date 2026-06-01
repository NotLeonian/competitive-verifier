(() => {
    const currentScript = document.currentScript;
    const mathjaxRoot = currentScript?.src
        ? new URL("../vendor/mathjax/es5", currentScript.src).href.replace(/\/$/, "")
        : "../vendor/mathjax/es5";

    window.MathJax = {
        tex: {
            tags: "ams",
            inlineMath: [['$', '$']],
            processEscapes: true,
            autoload: {
                color: [],
                colorv2: ['color']
            },
            packages: { '[+]': ['noerrors'] }
        },
        chtml: {
            matchFontHeight: false,
            displayAlign: "left",
            displayIndent: "2em"
        },
        options: {
            ignoreHtmlClass: 'tex2jax_ignore',
            processHtmlClass: 'tex2jax_process'
        },
        loader: {
            paths: {
                mathjax: mathjaxRoot,
                sre: `${mathjaxRoot}/a11y/sre`,
                mathmaps: `${mathjaxRoot}/a11y/mathmaps`
            },
            load: ['input/asciimath', '[tex]/noerrors']
        }
    };
})();