document.addEventListener('DOMContentLoaded', function() {
    // ─── Gestion du thème (changement clair/sombre) ───
    // Récupère le bouton de changement de thème et ajoute un écouteur de clic
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            // Bascule la classe 'dark-mode' sur le body pour changer le thème
            document.body.classList.toggle('dark-mode');
            // Met à jour le cookie pour mémoriser le thème choisi (clair ou sombre)
            const theme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            document.cookie = `theme=${theme}; path=/; max-age=${60 * 60 * 24 * 365}`;
        });
    }

    // ─── Gestion des cartes de candidats (sélection sur la page de vote) ───
    // Permet de sélectionner un candidat en cliquant sur sa carte
    const candidateCards = document.querySelectorAll('.candidate-card');
    candidateCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Ignore le clic si c'est sur un lien à l'intérieur de la carte
            if (!e.target.closest('a')) {
                const radio = this.querySelector('input[type="radio"]');
                if (radio) {
                    // Sélectionne le bouton radio du candidat cliqué
                    radio.checked = true;
                    // Retire la sélection des autres cartes
                    candidateCards.forEach(c => c.classList.remove('selected'));
                    // Ajoute la classe selected à la carte cliquée
                    this.classList.add('selected');
                }
            }
        });
    });

    // ─── Affichage du candidat sélectionné sur la page de succès ───
    // Affiche le nom du candidat choisi dans le message de succès après le vote
    if (window.location.pathname.includes('success')) {
        const candidateId = new URLSearchParams(window.location.search).get('candidate_id');
        if (candidateId) {
            // Trouve l'élément du candidat sélectionné grâce à son id
            const candidateElement = document.querySelector(`.candidate-info input[value="${candidateId}"]`);
            if (candidateElement) {
                // Récupère le nom du candidat sélectionné
                const candidateName = candidateElement.closest('.candidate-info').querySelector('h3').textContent;
                // Remplace le texte générique par le nom du candidat dans le message de succès
                const successMessage = document.querySelector('.success-message');
                if (successMessage) {
                    successMessage.innerHTML = successMessage.innerHTML.replace('le candidat sélectionné', candidateName);
                }
            }
        }
    }

    // ─── Auto-fermeture des messages flash après 5 secondes ───
    // Les messages flash disparaissent automatiquement après 5 secondes
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 300);
        }, 5000);
    });

    // ─── Validation des formulaires (champs obligatoires) ───
    // Vérifie que tous les champs requis sont remplis avant la soumission du formulaire
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            // Vérifie que chaque champ requis est rempli
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    // Ajoute la classe 'error' si le champ est vide
                    field.classList.add('error');
                    isValid = false;
                } else {
                    field.classList.remove('error');
                }
            });

            // Affiche un toast d'erreur si un champ requis est vide et empêche l'envoi du formulaire
            if (!isValid) {
                e.preventDefault();
                Toastify({
                    text: "Veuillez remplir tous les champs obligatoires",
                    duration: 3000,
                    close: true,
                    gravity: "top",
                    position: "right",
                    backgroundColor: "linear-gradient(to right, #f72585, #b5179e)",
                    className: "toast-error"
                }).showToast();
            }
        });
    });

    // ─── Mise en surbrillance du ou des gagnants dans le tableau récapitulatif ───
    // Met en évidence la ou les lignes du tableau ayant le plus de votes
    const summaryTable = document.querySelector('.summary-table');
    if (summaryTable) {
        const rows = Array.from(summaryTable.querySelectorAll('tbody tr'));
        if (rows.length) {
            // Trouve le nombre de votes maximum parmi les candidats
            let maxVotes = 0;
            rows.forEach(row => {
                const votes = parseInt(row.cells[1].textContent, 10);
                if (votes > maxVotes) {
                    maxVotes = votes;
                }
            });
            // Ajoute la classe "winner" aux lignes ayant le nombre maximum de votes
            rows.forEach(row => {
                const votes = parseInt(row.cells[1].textContent, 10);
                if (votes === maxVotes) {
                    row.classList.add('winner');
                }
            });
        }
    }
});
