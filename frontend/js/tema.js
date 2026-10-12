/* Aplica o tema salvo antes de pintar a página, para não piscar. Fica fora do módulo de propósito. */
(function () {
    try {
        var salvo = localStorage.getItem('erp-tema');
        if (salvo === 'light' || salvo === 'dark') document.documentElement.dataset.theme = salvo;
    } catch (e) {}
})();
