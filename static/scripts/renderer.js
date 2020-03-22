function Renderer(variables = null, values = null, functions = null) {
    this.variables = variables === null ? {} : variables;
    this.values = values === null ? {} : values;
    this.functions = functions === null ? {} : functions;

    const localContext = (el, localVariables = null) => {
        localVariables = localVariables !== null ? localVariables : {};
        const ctxS = el.getAttribute('r-local-context');
        let ctx = {};
        if (ctxS !== null)
            ctx = JSON.parse(ctxS);
        return Object.assign(ctx, localVariables);
    };

    this.render = (element = null, localVariables = null) => {
        if (element === null) element = document.body;
        if (localVariables === null) localVariables = {};

        // noinspection JSUnusedLocalSymbols
        const v = this.variables;
        // noinspection JSUnusedLocalSymbols
        const w = this.values;
        // noinspection JSUnusedLocalSymbols
        const f = this.functions;

        // delete all previously rendered
        element.querySelectorAll('[r-child]').forEach(el =>
            el.parentElement.removeChild(el)
        );

        // assign clicks
        element.querySelectorAll('[r-click]').forEach(el =>
            el.onclick = () => {
                eval(el.getAttribute('r-click'));
            }
        );

        // render all variables
        element.querySelectorAll('[r-var]').forEach(el => {
                let val;
                try {
                    const l = localContext(el, localVariables);
                    val = eval(el.getAttribute('r-var'));
                    el.setAttribute('r-local-context', JSON.stringify(l));
                } catch {
                    val = '';
                }
                el.textContent = `${val}`;
            }
        );

        // render attributes
        element.querySelectorAll('[r-attr]').forEach(el => {
                const l = localContext(el, localVariables);
                const attrs = JSON.parse(el.getAttribute('r-attr'));
                Object.keys(attrs).forEach(attr => {
                    let val;
                    try {
                        val = eval(attrs[attr]);
                    } catch {
                        val = '';
                    }
                    el.setAttribute(attr, `${val}`);
                });
                el.setAttribute('r-local-context', JSON.stringify(l));
            }
        );

        // render if's
        element.querySelectorAll('[r-if]').forEach(el => {
            const l = localContext(el, localVariables);
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
                renderedEl.removeAttribute('hidden');
                renderedEl.removeAttribute('disabled');

                renderedEl.setAttribute('r-local-context', JSON.stringify(l));
                this.renderString(renderedEl, el.dataset.content);
                this.renderElementHeaders(renderedEl, l);

                el.parentElement.insertBefore(renderedEl, el);
            }
        });

        // render for's
        element.querySelectorAll('[r-for]').forEach(el => {
            const parts = el.getAttribute('r-for').split(' of ');
            const forVar = parts[0];
            const l = localContext(el, localVariables);
            const array = eval(parts[1]) || [];

            array.forEach(x => {
                const renderedEl = el.cloneNode(false);
                renderedEl.classList.remove('r-hidden');
                delete renderedEl.dataset.index;
                delete renderedEl.dataset.content;
                renderedEl.removeAttribute('r-for');
                renderedEl.setAttribute('r-child', el.dataset.index);
                renderedEl.setAttribute('r-for-child', el.getAttribute('r-for'));
                renderedEl.removeAttribute('hidden');
                renderedEl.removeAttribute('disabled');

                const localVariablesCopy = Object.assign({}, l);
                localVariablesCopy[forVar] = x;
                renderedEl.setAttribute('r-local-context', JSON.stringify(localVariablesCopy));
                this.renderString(renderedEl, el.dataset.content, localVariablesCopy);
                this.renderElementHeaders(renderedEl, localVariablesCopy);

                el.parentElement.insertBefore(renderedEl, el);
            });
        });

        this.renderElementHeaders(element, localVariables);
    };

    this.renderString = (el, str, localVariables = null) => {
        el.innerHTML = str;
        this.render(el, localVariables);
        return el.innerHTML;
    };

    this.renderElementHeaders = (el, localVariables = null) => {
        if (localVariables === null) {
            const context = el.getAttribute('r-local-context');
            if (context !== null) {
                localVariables = JSON.parse(context);
            } else {
                localVariables = {};
            }
        }

        // noinspection JSUnusedLocalSymbols
        const v = this.variables;
        // noinspection JSUnusedLocalSymbols
        const l = localVariables;
        // noinspection JSUnusedLocalSymbols
        const w = this.values;
        // noinspection JSUnusedLocalSymbols
        const f = this.functions;

        const rVar = el.getAttribute('r-var');
        const rAttr = el.getAttribute('r-attr');

        if (rVar !== null) {
            let val;
            try {
                val = eval(el.getAttribute('r-var'));
            } catch {
                val = '';
            }
            el.textContent = val;
        }
        if (rAttr !== null) {
            const attrs = JSON.parse(rAttr);
            Object.keys(attrs).forEach(attr => el.setAttribute(attr, eval(attrs[attr]) || ''));
        }
    };

    // noinspection JSUnusedGlobalSymbols
    this.fetchAllValues = () => {
        // noinspection JSUnusedLocalSymbols
        const w = this.values;

        // fetch all values
        document.querySelectorAll('[r-val]').forEach(el => {
            // noinspection JSUnusedLocalSymbols
            const currValue = el.value || null;
            const variable = el.getAttribute('r-val');
            try {
                eval(`${variable} = currValue;`);
            } catch {
            }
        });
    };

    this.applyAllValues = () => {
        // noinspection JSUnusedLocalSymbols
        const w = this.values;

        document.querySelectorAll('[r-val]').forEach(el => {
            const variable = el.getAttribute('r-val');
            el.value = eval(variable) || '';
        });
    };

    this.getValue = (value) => {
        const el = document.querySelector(`[r-val="w.${value}"]`);
        if (!el) return null;
        return this.values[value] = el.value;
    };

    // noinspection JSUnusedGlobalSymbols
    this.setValue = (value, valueValue) => {
        this.values[value] = valueValue;
        document.querySelectorAll(`[r-val="w.${value}"]`).forEach(el => el.value = valueValue);
    };

    if (!!Object.keys(this.values).length) {
        this.applyAllValues();
    }

    const operands = [];

    ['r-for', 'r-if'].forEach(s => document.querySelectorAll(`[${s}]`).forEach(el => {
        operands.push(el);
    }));
    operands.reverse();

    operands.forEach((el, i) => {
        if (el.dataset.parsed === '1') return;

        el.dataset.content = el.innerHTML.trim();
        el.dataset.index = `${i}`;
        el.dataset.parsed = '1';
        el.setAttribute('hidden', 'true');
        el.setAttribute('disabled', 'true');
        el.classList.add('r-hidden');
        el.innerHTML = '';
    });

    const style = document.createElement('style');
    document.body.appendChild(style);
    style.innerHTML = `
    .r-hidden {
        visibility: hidden !important;
        position: fixed !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        top: -10000px !important;
        left: -10000px  !important;
    }
    `;

    if (!!Object.keys(this.variables).length) {
        this.render();
    }
}