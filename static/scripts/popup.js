function Popup(content, duration = null) {
    const el = document.createElement('div');
    el.classList.add('popup');
    el.classList.add('btn');
    el.classList.add('btn-lg');
    el.classList.add('btn-info');
    el.innerHTML = content;
    let shown = false;

    this.show = () => {
        if (shown)
            return;
        shown = true;
        document.body.appendChild(el);
        el.classList.add('popup-in');

        if (duration !== null)
            setTimeout(() => this.remove(), duration);
    };

    this.remove = () => {
        if (!shown)
            return;
        shown = false;
        el.classList.remove('popup-in');
        el.classList.add('popup-out');
        setTimeout(() => el.parentElement.removeChild(el), 1000);
    };
}