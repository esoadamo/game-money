function askText(message, type = 'text') {
    const el = document.createElement('div');
    const modalIDPrefix = 'modalAskText';
    let i = 0;
    let modalID;

    while (true) {
        modalID = `${modalIDPrefix}${i}`;
        if (document.querySelector(`#${modalID}`) === null)
            break;
        i ++;
    }

    el.innerHTML = `
<div id="${modalID}" class="modal fade" role="dialog">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-body">
                <label id="label" for="input"></label>
                <input id="input" class="form-control input-lg">
            </div>
            <div class="modal-footer">
                <button id="btnOK"
                        type="button" class="btn btn-success btn-lg" data-dismiss="modal">OK
                </button>
                <button id="btnCancel"
                        type="button" class="btn btn-default btn-lg" data-dismiss="modal">Cancel
                </button>
            </div>
        </div>
    </div>
</div>
`;
    const btnOK = el.querySelector('#btnOK');
    const btnCancel = el.querySelector('#btnCancel');
    const input = el.querySelector('#input');
    const label = el.querySelector('#label');

    document.body.appendChild(el);

    input.setAttribute('type', type);
    label.textContent = message;

    return new Promise(resolve => {
        let resolved = false;

        function r(v) {
            console.log('resolving with', v);
            if (resolved)
                return;
            resolved = true;
            resolve(v);
        }

        btnCancel.addEventListener('click', () => r(null));
        btnOK.addEventListener('click', () => r(input.value));

        const modal = $(`#${modalID}`);
        modal.on('hidden.bs.modal', () => {
            r(null);
            el.parentElement.removeChild(el);
        });
        modal.modal('show');
    });
}