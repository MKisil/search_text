import json
import os
import re
from pathlib import Path

import pymorphy2
import jinja2
from fuzzywuzzy import fuzz

morph = pymorphy2.MorphAnalyzer(lang='uk')


def search_keywords(k_words, text, src_text):
    count_kwords = 0
    indexes_kwords = {}

    def actions():
        nonlocal src_text, count_kwords
        match = re.search(rf'\W{{,2}}?{w}\W{{,2}}?', src_text)
        if not match:
            match = re.search(rf'\W{{,2}}?{kw}\W{{,2}}?', src_text)
            if not match:
                return
        found_word = match.group()
        indexes_kwords.setdefault(kw, []).append((match.start() + (len(found_word) - len(re.sub(r'^\W+', '', found_word))), match.end() - (len(found_word) - len(re.sub(r'^\W+', '', found_word[::-1])))))
        src_text = src_text.replace(found_word, '-' * len(found_word), 1)
        count_kwords += 1
        delete_word_from_text(w, text)

    for kw in k_words:
        normal_form_kw = morph.parse(kw)[0].normal_form
        for w in text:
            if fuzz.ratio(kw, w) > 65:
                normal_form_w = morph.parse(w)[0].normal_form
                if bool(re.match(rf'{kw}?[а-яіїєґ]{{,3}}', w)) or bool(re.match(rf'{w}[а-яіїєґ]{{,3}}\b', kw)):
                    actions()
                elif ('не' in w[:2] or 'не' in kw[:2]) and not ('не' in w[:2] and 'не' in kw[:2]):
                    continue
                elif bool(re.match(rf'{normal_form_kw}?[а-яіїєґ]{{,3}}', normal_form_w)):
                    actions()
                elif fuzz.ratio(normal_form_kw, normal_form_w) > 80:
                    actions()
                elif fuzz.ratio(kw, w) > 80:
                    actions()

    return count_kwords, indexes_kwords


def search_keyphrases(k_phrases, text, src_text):
    count_kphrases = 0
    indexes_kphrases = {}

    def actions(f_ph):
        nonlocal src_text, count_kphrases
        match = re.search(rf'\W{{,2}}?{f_ph}\W{{,2}}?', src_text)
        if not match:
            match = re.search(rf'\W{{,2}}?{ph}\W{{,2}}?', src_text)
            if not match:
                count_kphrases -= 1
                return
        found_ph = match.group()
        indexes_kphrases.setdefault(ph, []).append((match.start() + (len(found_ph) - len(re.sub(r'^\W+', '', found_ph))), match.end() - (len(found_ph) - len(re.sub(r'^\W+', '', found_ph[::-1])))))
        src_text = src_text.replace(found_ph, '-' * len(found_ph), 1)

    for ph in k_phrases:
        updated_text, phrases_cnt = re.subn(rf'\b{ph}[а-яіїєґ]{{,1}}', '', text)
        matches = list(re.finditer(rf'\b{ph}[а-яіїєґ]{{,1}}', text))
        text = updated_text

        for f_ph in [m.group() for m in matches]:
            actions(f_ph)

        phrase_words = ph.split()
        for i in range(len(text.split())):
            text_slice = " ".join(text.split()[i:i + len(phrase_words)])
            if fuzz.ratio(ph, text_slice) > 90 and ph.split()[0] == text_slice.split()[0]:
                actions(text_slice)
                phrases_cnt += 1

        count_kphrases += phrases_cnt

    return count_kphrases, indexes_kphrases


def delete_word_from_text(w, text):
    indx = text.index(w)
    text.remove(w)
    text.insert(indx, '')


def prepare_text(text, symbols_to_delete):
    text = text.lower().strip()
    for symbol in symbols_to_delete:
        text = text.replace(symbol, ' ')

    return text


def get_color_keywords(cnt_keywords, colors):
    for c in colors:
        diapason = c.split('-')[0].split(',')
        if len(diapason) == 2:
            if int(diapason[0]) <= cnt_keywords <= int(diapason[1]):
                return c.split('-')[1]
        elif len(diapason) == 1:
            if int(diapason[0]) <= cnt_keywords:
                return c.split('-')[1]


def search():
    directory_conversations_path = Path('conversations')
    conversations_files = sorted([file.name for file in directory_conversations_path.iterdir() if file.is_file()])
    directory_keywords_path = Path('keywords')
    keywords_files = sorted([file.name for file in directory_keywords_path.iterdir() if file.is_file()])

    while True:
        filename = input('Введіть назву файлу із якого потрібно почати(наприклад ria_00.txt): ')
        if filename in conversations_files:
            break
        elif filename == 'вийти':
            exit()
        else:
            print('Помилка. Введіть правильну назву файлу')

    if filename == conversations_files[0] or not os.path.isfile('./result.json'):
        index_filename = conversations_files.index(filename)
        conversations_files = conversations_files[index_filename:]
        result = {}
        result['keywords_files'] = [file.split('.')[0] for file in keywords_files]
        result['conversations_files'] = {}
    else:
        index_filename = conversations_files.index(filename)
        conversations_files = conversations_files[index_filename:]
        with open('result.json', encoding='utf-8') as file:
            result = json.loads(file.read())

    for conversation_file in conversations_files:
        print(f'Обробка файлу {conversation_file}')
        with open(f'conversations/{conversation_file}', 'r', encoding='utf-8') as file:
            text = file.read()
            src_convo_text = text.lower()
            conversation_text = prepare_text(text, ['- ',' - ',' -',',','.','?','!',';',':','…','_','«','»','*', '"']).split()

        text_for_search_phrases = " ".join(conversation_text)
        text_for_search_words = [w for w in conversation_text if len(w) > 2]

        indexes_kwords = {}
        indexes_kwords[conversation_file] = {}
        result['conversations_files'][conversation_file] = {}
        for keyword_file in keywords_files:
            with open(f'keywords/{keyword_file}', 'r', encoding='utf-8') as file:
                file_text = file.read()
                colors = file_text.strip().split('\n')[0].split()
                keywords = prepare_text(file_text, ['- ',' - ',' -',',','.','?','!',';',':','…','_','«','»','*', '"']).split('\n')[1:]
                k_words = sorted(set([i for i in keywords if ' ' not in i]), reverse=True)
                k_phrases = sorted(set([i for i in keywords if ' ' in i]), reverse=True)

            count_kwords, indexes_w = search_keywords(k_words, text_for_search_words, src_convo_text)
            count_kphrases, indexes_ph = search_keyphrases(k_phrases, text_for_search_phrases, src_convo_text)

            count = count_kwords + count_kphrases

            indexes_w.update(indexes_ph)

            indexes_kwords[conversation_file][keyword_file] = indexes_w if indexes_w else 'не знайдено слів'
            result['conversations_files'][conversation_file][keyword_file] = {
                "count": count,
                "len_text": len(conversation_text),
                "color": get_color_keywords(count, colors)
            }

        with open(f'conversations2/{conversation_file}', 'w', encoding='utf-8') as file:
            cnt = 0
            lst_indexes = []

            for indexes in indexes_kwords[conversation_file].values():
                if type(indexes) != str:
                    for index in indexes.values():
                        lst_indexes += index

            lst_indexes2 = []
            for i in lst_indexes:
                included_in_j = False
                for j in lst_indexes:
                    if i[0] >= j[0] and i[1] <= j[1] and i != j:
                        included_in_j = True
                        break
                if not included_in_j:
                    lst_indexes2.append(i)

            for i in sorted(lst_indexes2):
                text = text[:i[0]+cnt] + '<b>' + text[i[0]+cnt:i[1]+cnt] + '</b>' + text[i[1]+cnt:]
                cnt += 7

            file.write(text)

        with open(f'indexes_kwords/{conversation_file}', 'w', encoding='utf-8') as file:
            for keyword_file, indexes in indexes_kwords[conversation_file].items():
                file.write(f"{keyword_file}: {indexes}\n")

        with open('result.json', 'w', encoding='utf-8') as file:
            json.dump(result, file, indent=2, ensure_ascii=False)

    print('Завершено.')


def generate_html():
    with open('result.json', encoding='utf-8') as file:
        data = json.loads(file.read())

    with open('result/template.html', encoding='utf-8') as file:
        html_template = file.read()

    template = jinja2.Template(html_template)
    html = template.render(data=data)

    with open('result/result.html', 'w', encoding='utf-8') as file:
        file.write(html)


if __name__ == '__main__':
    search()
    generate_html()
