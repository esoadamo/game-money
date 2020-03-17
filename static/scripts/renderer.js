function Renderer(variables = null) {
    this.variables = variables === null ? {} : variables;

    this.render = (element = null, localVariables = null) => {
        if (element === null) element = document.body;
        if (localVariables === null) localVariables = {};

        // noinspection JSUnusedLocalSymbols
        const v = this.variables;
        // noinspection JSUnusedLocalSymbols
        const l = localVariables;

        // delete all previously rendered
        element.querySelectorAll('[r-child]').forEach(el =>
            el.parentElement.removeChild(el)
        );

        // render all variables
        element.querySelectorAll('[r-var]').forEach(
            el => el.textContent = `${eval(el.getAttribute('r-var'))}`
        );

        // render if's
        element.querySelectorAll('[r-if]').forEach(el => {
            let render = false;
            try {
                render = !!eval(el.getAttribute('r-if'));
            } catch {
            }

            if (render) {
                const renderedEl = el.cloneNode(false);
                renderedEl.classList.remove('r-hidden');
                delete renderedEl.dataset.index;
                delete renderedEl.dataset.content;
                renderedEl.removeAttribute('r-if');
                renderedEl.setAttribute('r-child', el.dataset.index);
                renderedEl.setAttribute('r-if-child', el.getAttribute('r-if'));

                this.renderString(renderedEl, el.dataset.content);

                el.parentElement.insertBefore(renderedEl, el);
            }
        });

        // render for's
        element.querySelectorAll('[r-for]').forEach(el => {
            const parts = el.getAttribute('r-for').split(' of ');
            const forVar = parts[0];
            const array = eval(parts[1]);

            array.forEach(x => {
                const renderedEl = el.cloneNode(false);
                renderedEl.classList.remove('r-hidden');
                delete renderedEl.dataset.index;
                delete renderedEl.dataset.content;
                renderedEl.removeAttribute('r-for');
                renderedEl.setAttribute('r-child', el.dataset.index);
                renderedEl.setAttribute('r-if-child', el.getAttribute('r-for'));

                const localVariablesCopy = Object.assign({}, localVariables);
                localVariablesCopy[forVar] = x;
                this.renderString(renderedEl, el.dataset.content, localVariablesCopy);

                el.parentElement.insertBefore(renderedEl, el);
            });
        });
    };

    this.renderString = (el, str, localVariables = null) => {
        el.innerHTML = str;
        this.render(el, localVariables);
        return el.innerHTML;
    };

    const operands = [];

    ['r-for', 'r-if'].forEach(s => document.querySelectorAll(`[${s}]`).forEach(el => {
        operands.push(el);
    }));

    operands.forEach((el, i) => {
        if (el.dataset.parsed === '1') return;

        el.dataset.content = el.innerHTML.trim();
        el.dataset.index = `${i}`;
        el.dataset.parsed = '1';
        el.classList.add('r-hidden');
        el.innerHTML = '';
    });

    const style = document.createElement('style');
    document.body.appendChild(style);
    style.innerHTML = `
    .r-hidden {
        visibility: hidden !important;
        position: absolute !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        top: -10000px !important;
        left: -10000px  !important;
    }
    `;
}