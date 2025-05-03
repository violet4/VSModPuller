#!/usr/bin/env python
# coding: utf-8
from typing import Optional
import datetime
import enum
import pathlib
import json

import requests

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy import ForeignKey, String, TypeDecorator, Integer, Enum, create_engine

from sqlalchemy import TypeDecorator, create_engine, String, Integer
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


this_dir = pathlib.Path(__file__).resolve().parent
mods_file = this_dir / 'mods.json'
authors_file = this_dir / 'authors.json'

def download_load_data(url: str, filepath: pathlib.Path, key: str):
    if not filepath.exists():
        print(f"Downloading:\n    {url}\n    {filepath}")
        mods_resp = requests.get(url)
        mods_response_json = mods_resp.json()
        mods = mods_response_json[key]
        with filepath.open('w') as fw:
            json.dump(mods, fw)

    with filepath.open('r') as fr:
        mods = json.loads(fr.read())

    return mods


def str_to_datetime(datestr):
    try:
        return datetime.datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        print(e)
        raise


class UnixTimestamp(TypeDecorator):
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: Optional[int|str], _):
        if value is None:
            return None
        if isinstance(value, str):
            return str_to_datetime(value).timestamp()
        return int(datetime.datetime.timestamp(value))

    def process_result_value(self, value: Optional[datetime.datetime], _):
        if value is None:
            return None
        if isinstance(value, str):
            return str_to_datetime(value).timestamp()
        return datetime.datetime.fromtimestamp(value)


class Base(DeclarativeBase):
    def attr_str(self, attrs: list[str]) -> str:
        return ', '.join(f"{k}={getattr(self, k)}" for k in attrs)


class InstallSide(enum.StrEnum):
    server = enum.auto()
    client = enum.auto()
    both = enum.auto()


class ModType(enum.StrEnum):
    mod = enum.auto()
    externaltool = enum.auto()
    other = enum.auto()


class Author(Base):
    __tablename__ = 'author'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    mods: Mapped[list['Mod']] = relationship(back_populates='author')
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.attr_str(['id', 'name'])})"


class ModIdStr(Base):
    __tablename__ = 'modid_str'

    modid_str: Mapped[str] = mapped_column(primary_key=True)
    mod_id: Mapped[int] = mapped_column(ForeignKey('mod.id'))

    mod: Mapped['Mod'] = relationship(back_populates='modid_strs')

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.attr_str(['modid_str', 'mod_id'])})"


class ModTag(Base):
    __tablename__ = 'mod_tag'

    id: Mapped[int] = mapped_column(primary_key=True)
    mod_id: Mapped[int] = mapped_column(ForeignKey('mod.id'))
    tag_id: Mapped[int] = mapped_column(ForeignKey('tag.id'))


class ModVersion(Base):
    __tablename__ = 'mod_version'

    id: Mapped[int] = mapped_column(primary_key=True)
    mod_id: Mapped[int] = mapped_column(ForeignKey('mod.id'))
    version: Mapped[str] = mapped_column(unique=True)

    mod: Mapped['Mod'] = relationship(back_populates='versions')

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.attr_str(['version'])})"


class Mod(Base):
    __tablename__ = 'mod'

    id: Mapped[int] = mapped_column(primary_key=True)
    assetid: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String)
    summary: Mapped[Optional[str]] = mapped_column(String)

    author_id: Mapped[int] = mapped_column(ForeignKey('author.id'))
    author: Mapped['Author'] = relationship(back_populates='mods')

    urlalias: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    downloads: Mapped[int] = mapped_column(Integer)
    follows: Mapped[int] = mapped_column(Integer)
    trendingpoints: Mapped[int] = mapped_column(Integer)
    comment_count: Mapped[int] = mapped_column(Integer)
    logo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    side: Mapped[InstallSide] = mapped_column(Enum(InstallSide))
    mod_type: Mapped[ModType] = mapped_column(Enum(ModType))
    lastreleased: Mapped[UnixTimestamp] = mapped_column(UnixTimestamp)

    modid_strs: Mapped[list['ModIdStr']] = relationship(back_populates='mod')
    tags: Mapped[list['Tag']] = relationship(secondary='mod_tag', back_populates='mods')
    versions: Mapped[list[ModVersion]] = relationship(back_populates='mod')

    def __repr__(self) -> str:
        attrs = self.attr_str(['id', 'assetid', 'name', 'summary', 'urlalias', 'downloads',
                               'follows', 'trendingpoints', 'comment_count', 'logo', 'side',
                               'mod_type', 'lastreleased'])
        return f"{self.__class__.__name__}({attrs})"


class Tag(Base):
    __tablename__ = 'tag'

    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(unique=True)

    mods: Mapped[list[Mod]] = relationship(secondary='mod_tag', back_populates='tags')

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.attr_str(['tag'])})"


def main():
    mods = download_load_data('https://mods.vintagestory.at/api/mods', mods_file, 'mods')
    authors = download_load_data('https://mods.vintagestory.at/api/authors', authors_file, 'authors')
    # authors_by_id = {a['userid']: a for a in authors}
    authors_by_name = {a['name']: a for a in authors if a['name'] is not None}

    engine = create_engine('sqlite:///./vintage_story_mods.sqlite3')
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)

    session = Session()
    author = session.query(Author).filter(Author.name=='theysa').one_or_none()
    for mod in author.mods:
        print(mod)
        for version in mod.versions:
            print(version)
        for tag in mod.tags:
            print(tag)
        for modid_str in mod.modid_strs:
            print(modid_str)

    print(author)
    exit()


    for mod_dict in mods:
        mod_id_strs = mod_dict.pop('modidstrs', [])
        tag_strs = mod_dict.pop('tags', [])

        author_dict = authors_by_name[mod_dict.pop('author')]
        author = session.query(Author).filter(Author.id==author_dict['userid']).one_or_none()
        if author is None:
            userid = author_dict.get('userid')
            author = Author(id=userid, name=author_dict['name'])
            session.add(author)
            session.commit()

        modid = mod_dict.pop('modid')
        mod = session.query(Mod).filter(Mod.id==modid).one_or_none()
        if mod is None:
            # rename comments to comment_count
            mod_dict['comment_count'] = mod_dict.pop('comments')
            mod_dict['mod_type']= mod_dict.pop('type')
            mod = Mod(id=modid, author=author, **mod_dict)
            session.add(mod)
            session.commit()

        for mod_str in mod_id_strs:
            mod_id_str = session.query(ModIdStr).filter(ModIdStr.modid_str==mod_str).one_or_none()
            if mod_id_str is None:
                mod_id_str = ModIdStr(modid_str=mod_str, mod=mod)
                session.add(mod_id_str)
                session.commit()

        for tag_str in tag_strs:
            tag = session.query(Tag).filter(Tag.tag==tag_str).one_or_none()
            if tag is None:
                tag = Tag(tag=tag_str)
                session.add(tag)
                session.commit()
            mod.tags.append(tag)
        session.commit()
        # for version_str in mod_version_strs:
        #     mod_version = ModVersion(mod_id=mod.id, version=verion_str)
        #     session.add(mod_version)
        # session.commit()

    session.close()

if __name__ == '__main__':
    main()

