/**
 * Builds both counterbalanced survey forms in one run.
 *
 * HOW TO RUN
 *   1. https://script.google.com/home/projects/create
 *   2. Select everything in the editor (Ctrl+A) and paste this over it.
 *   3. Ctrl+S to save.
 *   4. Click Run. The dropdown next to it should say createSurveyForms --
 *      it is the only runnable function in this file, on purpose.
 *   5. First run only: Review permissions -> your account -> Advanced ->
 *      Go to ... (unsafe) -> Allow. "Unsafe" only means the script is
 *      unpublished, i.e. it is yours.
 *   6. The Execution log ("Журнал выполнения") prints all four links.
 *
 * The helper is deliberately nested inside createSurveyForms. A previous
 * version had it at the top level, where Apps Script offered it in the Run
 * dropdown and ran it with no arguments -- "Invalid argument: title".
 *
 * Text is verbatim from survey/FORMS.md. Do not edit here without editing
 * there too.
 */

function createSurveyForms() {

  var INTRO =
    'Опрос занимает 3–5 минут и полностью анонимный. Мы не собираем имена, ' +
    'контакты и любые данные, позволяющие вас идентифицировать. Ответы ' +
    'используются в школьном исследовательском проекте только в обобщённом ' +
    'виде. Участие добровольное — вы можете закрыть форму в любой момент, ' +
    'ответы не будут сохранены.';

  var SCENARIO =
    'Два человека участвовали в задании. Участнику A выдали $100, и он должен ' +
    'был разделить их между собой и участником B. Участник B не мог влиять на ' +
    'решение. Участник A решил оставить себе $80 и отдать $20 участнику B.\n\n' +
    'Представьте, что вы — участник B. Отдельно от этого дележа у вас есть ' +
    'свои $50.\n\n' +
    'Дальше вам будет предложено несколько ситуаций. В каждой вы можете либо ' +
    'ничего не делать, либо заплатить часть своих денег, чтобы уменьшить ' +
    'выигрыш участника A. Рассматривайте каждую ситуацию независимо от остальных.';

  // The dollar figures must match what the harness renders: the punisher's
  // $50 wallet minus the cost, and A's $80 minus the damage.
  var ITEMS = {
    c1: 'Заплатить $5, чтобы участник A потерял $15. У вас останется $45, у участника A — $65.',
    c2: 'Заплатить $10, чтобы участник A потерял $20. У вас останется $40, у участника A — $60.',
    c3: 'Заплатить $15, чтобы участник A потерял $15. У вас останется $35, у участника A — $65.',
    c4: 'Заплатить $20, чтобы участник A потерял $10. У вас останется $30, у участника A — $70.'
  };

  var ATTENTION =
    'Этот вопрос проверяет внимательность чтения. Выберите вариант «Ничего не делать».';

  var OPEN_Q = 'Что повлияло на ваши решения? (необязательно)';

  var CHOICES = ['Ничего не делать', 'Заплатить'];

  /**
   * @param {string} title
   * @param {string[]} order Condition ids in presentation order. The
   *     attention check goes after the second item, per the locked design.
   */
  function buildForm(title, order) {
    if (!title || typeof title !== 'string') {
      throw new Error(
        'buildForm needs a title. Run createSurveyForms, not this helper.'
      );
    }

    var form = FormApp.create(title);

    form.setDescription(INTRO);

    // Anonymity is a claim the paper makes, so these are not optional.
    form.setCollectEmail(false);
    form.setLimitOneResponsePerUser(false); // would force sign-in
    form.setProgressBar(true);
    form.setAllowResponseEdits(false);
    form.setPublishingSummary(false);

    form.addPageBreakItem().setTitle('Ситуация').setHelpText(SCENARIO);

    for (var i = 0; i < order.length; i++) {
      if (i === 2) {
        form.addMultipleChoiceItem()
          .setTitle(ATTENTION)
          .setChoiceValues(CHOICES)
          .setRequired(true);
      }
      form.addMultipleChoiceItem()
        .setTitle(ITEMS[order[i]])
        .setChoiceValues(CHOICES)
        .setRequired(true);
    }

    form.addParagraphTextItem().setTitle(OPEN_Q).setRequired(false);

    return form;
  }

  // Version 1 ascending price, version 2 descending. Alternating them between
  // respondents is what removes the demand characteristic the v1 survey had,
  // where everyone saw the same ascending ladder.
  var v1 = buildForm(
    'Исследование: решения в экономической задаче (версия 1)',
    ['c1', 'c2', 'c3', 'c4']
  );
  var v2 = buildForm(
    'Исследование: решения в экономической задаче (версия 2)',
    ['c4', 'c3', 'c2', 'c1']
  );

  var out = [
    '',
    '=== SEND THESE TWO LINKS TO RESPONDENTS ===',
    '',
    'Version 1 (ascending):  ' + v1.getPublishedUrl(),
    'Version 2 (descending): ' + v2.getPublishedUrl(),
    '',
    '=== EDIT THE FORMS HERE ===',
    '',
    'v1 edit: ' + v1.getEditUrl(),
    'v2 edit: ' + v2.getEditUrl(),
    '',
    'Alternate who gets which. Target 30-40 responses total.',
    ''
  ].join('\n');

  Logger.log(out);
  return out;
}
