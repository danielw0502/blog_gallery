# -*-coding: utf-8-*-
import sys
import datetime
import functools
import os
import re
import urllib
from flask import (Flask, flash, Markup, redirect, render_template, request,
                   Response, session, url_for)
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from micawber import bootstrap_basic, parse_html
from micawber.cache import Cache as OEmbedCache
from peewee import *
from playhouse.flask_utils import FlaskDB, get_object_or_404, object_list
from playhouse.sqlite_ext import *


import time
from flask_bootstrap import Bootstrap
import PIL
import hashlib
from PIL import Image
from flask import current_app, send_from_directory
from flask_wtf import Form
from wtforms import StringField, SubmitField, FileField, TextAreaField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from flask_uploads import UploadSet, configure_uploads, IMAGES

# Blog configuration values.

# You may consider using a one-way hash to generate the password, and then
# use the hash again in the login view to perform the comparison. This is just
# for simplicity.
ADMIN_PASSWORD = 'secret'
APP_DIR = os.path.dirname(os.path.realpath(__file__))

# The playhouse.flask_utils.FlaskDB object accepts database URL configuration.
DATABASE = 'sqliteext:///%s' % os.path.join(APP_DIR, 'blog.db')
DEBUG = False

# The secret key is used internally by Flask to encrypt session data stored
# in cookies. Make this unique for your app.
SECRET_KEY = 'shhh, secret!'

# This is used by micawber, which will attempt to generate rich media
# embedded objects with maxwidth=800.
SITE_WIDTH = 800


# Create a Flask WSGI app and configure it using values from the module.
app = Flask(__name__)
app.config.from_object(__name__)

#xianda add

bootstrap = Bootstrap(app)

app.config['UPLOADED_PHOTOS_DEST'] = os.getcwd() + '/static/images'
#xianda add

# FlaskDB is a wrapper for a peewee database that sets up pre/post-request
# hooks for managing database connections.
flask_db = FlaskDB(app)

# The `database` is the actual peewee database, as opposed to flask_db which is
# the wrapper.
database = flask_db.database

# Configure micawber with the default OEmbed providers (YouTube, Flickr, etc).
# We'll use a simple in-memory cache so that multiple requests for the same
# video don't require multiple network requests.
oembed_providers = bootstrap_basic(OEmbedCache())


def login_required(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if session.get('logged_in'):
            return fn(*args, **kwargs)
        return redirect(url_for('login', next=request.path))
    return inner


#xianda add 0811 begin
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)

class Album(flask_db.Model):
    id = IntegerField(primary_key = True)
    title = CharField() #相册标题
    about = TextField() #相册信息
    cover = CharField() # 相册封面图片url
    timestamp = DateTimeField(default=datetime.datetime.now)
    class Meta:
        database = database
    
class Photo(flask_db.Model):
    #id = IntegerField(primary_key = True)
    #order = IntegerField()
    url = CharField() #原图url
    url_s = CharField() #展示图url
    url_t = CharField() #缩略图url
    #about = TextField() #图片介绍
    timestamp = DateTimeField(default=datetime.datetime.now)
    album_id = ForeignKeyField(Album, backref='photos')
    class Meta:
        database = database
        
#上传表单begin
class NewAlbumForm(Form):
    title = StringField('title')
    about = TextAreaField('introduction', render_kw ={'rows': 8})
    photo = FileField('photo', validators=[FileRequired('you have not choose picture'), FileAllowed(photos, 'photo only')])
    submit = SubmitField('submit')

class AddPhotoForm(Form):
    photo = FileField('picture', validators=[FileRequired(),FileAllowed(photos, 'photo only')])
    submit = SubmitField('submit')
#上传表单end

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOADED_PHOTOS_DEST'],filename)

img_suffix = {
    300: '_t',
    800: '_s'
}

def image_resize(image, base_width):
    filename, ext = os.path.splitext(image)
    img = Image.open(photos.path(image))
    if img.size[0] <= base_width:
        return photos.url(image)
    w_percent = (base_width / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)))
    img = img.resize((base_width, h_size), PIL.Image.ANTIALIAS)
    img.save(os.path.join(current_app.config['UPLOADED_PHOTOS_DEST'], filename + img_suffix[base_width] + ext))
    return url_for('.uploaded_file', filename=filename + img_suffix[base_width] + ext)

#image save
def save_image(files):
    images = []
    for img in files:
        filename = hashlib.md5(str(time.time())).hexdigest()[:10]
        image = photos.save(img, name=filename + '.')
        file_url = photos.url(image)
        url_s = image_resize(image, 800) #创建展示图
        url_t = image_resize(image, 300) #创建缩略图
        images.append((file_url, url_s , url_t))
    return images

@app.route('/gallery', methods=['GET', 'POST'])
def gallery():
    albums = Album.select()
    return render_template('gallery.html', albums=albums)

#0818 add (wait to debug)
@app.route('/album/<int:id>',methods=['GET','POST'])
def album(id):
    album = Album.get(Album.id == id)
    placeholder = 'http://p1.bpimg.com/567591/15110c0119201359.png'
    photo_amount = len(list(album.photos))
    print 
    if photo_amount == 0:
        album.cover = placeholder
    elif photo_amount != 0 and album.cover == placeholder:
        album.cover = album.photos[0].path
    
    page = request.args.get('page', 1, type=int)
    pagination = album.photos.order_by(Photo.id.asc()).paginate(page, 5)
    #photos = pagination.items
    photos = album.photos
    return render_template('album.html', album=album, photos=photos, pagination=pagination)
#not debug

@app.route('/upload', methods=['GET','POST'])
@login_required
def upload():
    albums = Album.select()
    return render_template('upload.html',albums=albums)

@app.route('/upload-add', methods=['GET','POST'])
@login_required
def upload_add():
    id = request.form.get('album')
    return redirect(url_for('.add_photo',id=id))

def get_current_album(album):
    return Album.get(Album.title == album.title)

@app.route('/create_gallery', methods=['GET', 'POST'])
@login_required
def create_gallery():
    form = NewAlbumForm()
    if form.validate_on_submit():
        if request.method == 'POST' and 'photo' in request.files:
            images = save_image(request.files.getlist('photo'))
        
        title = form.title.data
        about = form.about.data

        cover = images[0][2]
        album = Album(title = title, about = about, cover = cover)
        album.save()
        album_c = get_current_album(album)
        #db.session.add(album)
        for url in images:
            photo = Photo.create(url=url[0], url_s = url[1], url_t = url[2], album_id = album_c)
            #
            #photo.save()
            #db.session.add(photo)
        #db.session.commit()
        flash('successful', 'success')
        print album_c.id
        return redirect(url_for('.album', id=album_c.id))
    return render_template('create_gallery.html', form=form)

@app.route('/photo/<int:id>', methods=['GET','POST'])
def photo(id):
    photo = Photo.select().where(Photo.id == id).get()
    album = photo.album_id
    photo_sum = len(list(album.photos))
    photo_index = [p.id for p in album.photos.order_by(Photo.id.asc())].index(photo.id) + 1
    page = request.args.get('page', 1, type=int)
    return render_template('photo.html', album=album, photo=photo,photo_index=photo_index, photo_sum=photo_sum)
    

@app.route('/photo/p/<int:id>')
def photo_previous(id):
    "redirect to previous image"
    photo_now = Photo.select().where(Photo.id == id).get()
    album = photo_now.album_id
    photos = album.photos.order_by(Photo.id.asc())
    position = list(photos).index(photo_now) - 1
    if position == -1:
        flash('first photo', 'info')
        return redirect(url_for('.photo', id=id))
    photo = photos[position]
    return redirect(url_for('.photo', id=photo.id))

@app.route('/photo/n/<int:id>')
def photo_next(id):
    "redirect to next image"
    photo_now = Photo.select().where(Photo.id == id).get()
    album = photo_now.album_id
    photos = album.photos.order_by(Photo.id.asc())
    position = list(photos).index(photo_now) + 1
    if position == len(list(photos)):
        flash('last photo', 'info')
        return redirect(url_for('.photo', id=id))
    photo = photos[position]
    return redirect(url_for('.photo', id=photo.id))


@app.route('/add-photo/<int:id>', methods=['GET','POST'])
@login_required
def add_photo(id):
    #album = Album.query.get_or_404(id)
    album = Album.get(Album.id == id)
    form = AddPhotoForm()
    if form.validate_on_submit():
        if request.method == 'POST' and 'photo' in request.files:
            images = save_image(request.files.getlist('photo'))
            for url in images:
                photo = Photo(url=url[0], url_s = url[1], url_t=url[2] , album_id = album)
                photo.save()
        flash('successful','success')
        return redirect(url_for('.album', id=album.id))
    return render_template('add_photo.html', form=form, album=album)

#xinda add 0811 end

class Entry(flask_db.Model):
    title = CharField()
    slug = CharField(unique=True)
    content = TextField()
    published = BooleanField(index=True)
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)
    tag_name = CharField()
    @property
    def html_content(self):
        """
        Generate HTML representation of the markdown-formatted blog entry,
        and also convert any media URLs into rich media objects such as video
        players or images.
        """
        hilite = CodeHiliteExtension(linenums=False, css_class='highlight')
        extras = ExtraExtension()
        markdown_content = markdown(self.content, extensions=[hilite, extras])
        oembed_content = parse_html(
            markdown_content,
            oembed_providers,
            urlize_all=True,
            maxwidth=app.config['SITE_WIDTH'])
        return Markup(oembed_content)

    def save(self, *args, **kwargs):
        # Generate a URL-friendly representation of the entry's title.
        if not self.slug:
            self.slug = self.title.encode('utf-8')
            #self.slug = self.title.lower().encode('utf-8')
            #print self.id
            #self.slug = re.sub('[^\w]+', '-', self.title.lower()).strip('-')
        ret = super(Entry, self).save(*args, **kwargs)

        # Store search content.
        self.update_seaverch_index()
        return ret

    def update_search_index(self):
        # Create a row in the FTSEntry table with the post content. This will
        # allow us to use SQLite's awesome full-text search extension to
        # search our entries.
        exists = (FTSEntry
                  .select(FTSEntry.docid)
                  .where(FTSEntry.docid == self.id)
                  .exists())
        content = '\n'.join((self.title, self.content))
        if exists:
            (FTSEntry
             .update({FTSEntry.content: content})
             .where(FTSEntry.docid == self.id)
             .execute())
        else:
            FTSEntry.insert({
                FTSEntry.docid: self.id,
                FTSEntry.content: content}).execute()

    @classmethod
    def public(cls):
        return Entry.select().where(Entry.published == True)

    @classmethod
    def drafts(cls):
        return Entry.select().where(Entry.published == False)

    @classmethod
    def search(cls, query):
        words = [word.strip() for word in query.split() if word.strip()]
        if not words:
            # Return an empty query.
            return Entry.select().where(Entry.id == 0)
        else:
            search = ' '.join(words)

        # Query the full-text search index for entries matching the given
        # search query, then join the actual Entry data on the matching
        # search result.
        return (Entry
                .select(Entry, FTSEntry.rank().alias('score'))
                .join(FTSEntry, on=(Entry.id == FTSEntry.docid))
                .where(
                    FTSEntry.match(search) &
                    (Entry.published == True))
                .order_by(SQL('score')))


class FTSEntry(FTSModel):
    content = TextField()

    class Meta:
        database = database

def img(img_path):
    import base64

    img_stream = ''
    
    with open(img_path, 'r') as img_f:
        img_stream = img_f.read()
        img_stream = base64.b64encode(img_stream)

    return img_stream

img_path = os.getcwd() + '/Wechat.png'
img_stream = img(img_path)


img_path1 = os.getcwd() + '/img/photo.png'
img_stream1 = img(img_path1)





@app.route('/login_test/', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST' and request.form.get('password'):
        password = request.form.get('password')
        # TODO: If using a one-way hash, you would also hash the user-submitted
        # password and do the comparison on the hashed versions.
        if password == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            session.permanent = True  # Use cookie to store session.
            flash('You are now logged in.', 'success')
            return redirect(next_url or url_for('index'))
        else:
            flash('Incorrect password.', 'danger')
    return render_template('login.html', next_url=next_url)

@app.route('/logout/', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.clear()
        return redirect(url_for('login'))
    return render_template('logout.html')

@app.route('/about')
def about():
    return render_template('about.html',img1 = img_stream1)




@app.route('/')
def index():
    search_query = request.args.get('q')
    if search_query:
        query = Entry.search(search_query)
    else:
        query = Entry.public().order_by(Entry.timestamp.desc())
    
    # The `object_list` helper will take a base query and then handle
    # paginating the results if there are more than 20. For more info see
    # the docs:
    # http://docs.peewee-orm.com/en/latest/peewee/playhouse.html#object_list
    query_tag = Entry.select(Entry.tag_name).distinct()
    tag_dict = dict()
    for e in query_tag:
        l = e.tag_name.strip('|').split('|')
        for ii in l:
            if ii in tag_dict:
                tag_dict[ii] += 1
            else:
                tag_dict[ii] = 1
    #display recently 5 articles
    query_article = Entry.public().order_by(Entry.timestamp.desc())
    ii = 1
    ll_article = []
    for kk in query_article:
        if ii <= 5:
            ll_article.append(kk.title)
        ii += 1
    return object_list(
        'index.html',
        query,
        t = tag_dict,
        recent_article = ll_article,
        search=search_query,
        paginate_by=12,
        img = img_stream,
        check_bounds=False)

    

def _create_or_edit(entry,template):
    if request.method == 'POST':
        entry.tag_name = request.form.get('tag_name') or ''
        entry.title = request.form.get('title') or ''
        entry.content = request.form.get('content') or ''
        entry.published = request.form.get('published') or False
        if not (entry.title and entry.content):
            flash('Title and Content are required.', 'danger')
        else:
            # Wrap the call to save in a transaction so we can roll it back
            # cleanly in the event of an integrity error.
            try:
                with database.atomic():
                    entry.save()
            except IntegrityError:
                flash('Error: this title is already in use.', 'danger')
            else:
                flash('Entry saved successfully.', 'success')
                if entry.published:
                    return redirect(url_for('detail', slug=entry.slug))
                else:
                    return redirect(url_for('edit', slug=entry.slug))

    return render_template(template, entry=entry)


@app.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    return _create_or_edit(Entry(title='', content=''),'create.html')

@app.route('/tag/<tag>')
def find_blog_with_tag(tag):
    python_entries = (Entry.select().where((Entry.published == True) & (Entry.tag_name.contains('|'+tag+'|'))))
    query_tag = Entry.select(Entry.tag_name).distinct()
    tag_dict = dict()
    for e in query_tag:
        l = e.tag_name.strip('|').split('|')
        for ii in l:
            if ii in tag_dict:
                tag_dict[ii] += 1
            else:
                tag_dict[ii] = 1
    query = Entry.public().order_by(Entry.timestamp.desc())
    #display recently 5 articles
    ii = 1
    ll_article = []
    for kk in query:
        if ii <= 5:
            ll_article.append(kk.title)
        ii += 1

    return object_list('index.html', python_entries, t= tag_dict,recent_article = ll_article,paginate_by=12, img = img_stream,check_bounds=False)

@app.route('/archives')
def distinct_tag():
    query_tag = (Entry.select(Entry.tag_name).distinct())
    #tag = (Entry.get_tag())
    tag_dict = dict()
    for e in query_tag:
        l = e.tag_name.strip('|').split('|')
        for ii in l:
            if ii in tag_dict:
                tag_dict[ii] += 1
            else:
                tag_dict[ii] = 1
    query = Entry.public().order_by(Entry.timestamp.desc())
    #display recently 5 articles
    ii = 1
    ll_article = []
    for kk in query:
        if ii <= 5:
            ll_article.append(kk.title)
        ii += 1

    return object_list('index.html', query_tag,t = tag_dict,recent_article = ll_article,paginate_by=12,img = img_stream,check_bounds=False)

@app.route('/drafts/')
@login_required
def drafts():
    query = Entry.drafts().order_by(Entry.timestamp.desc())
    tag_dict = dict()
    query_tag = Entry.select(Entry.tag_name).distinct()
    for e in query_tag:
        l = e.tag_name.strip('|').split('|')
        for ii in l:
            if ii in tag_dict:
                tag_dict[ii] += 1
            else:
                tag_dict[ii] = 1
    query_title = Entry.public().order_by(Entry.timestamp.desc())
    #display recently 5 articles
    ii = 1
    ll_article = []
    for kk in query_title:
        if ii <= 5:
            ll_article.append(kk.title)
        ii += 1

    return object_list('index.html', query, t = tag_dict,recent_article = ll_article,paginate_by=12,img = img_stream, check_bounds=False)

@app.route('/<slug>/')
def detail(slug):
    if session.get('logged_in'):
        query = Entry.select()
    else:
        query = Entry.public()
    entry = get_object_or_404(query, Entry.title == slug)
    
    tag_dict = dict()
    query_tag = Entry.select(Entry.tag_name).distinct()
    for e in query_tag:
        l = e.tag_name.strip('|').split('|')
        for ii in l:
            if ii in tag_dict:
                tag_dict[ii] += 1
            else:
                tag_dict[ii] = 1
    query_title = Entry.public().order_by(Entry.timestamp.desc())
    #display recently 5 articles
    ii = 1
    ll_article = []
    for kk in query_title:
        if ii <= 5:
            ll_article.append(kk.title)
        ii += 1

    return render_template('detail.html', t = tag_dict,recent_article = ll_article,img = img_stream,entry=entry)

@app.route('/<slug>/edit/', methods=['GET', 'POST'])
@login_required
def edit(slug):
    entry = get_object_or_404(Entry, Entry.slug == slug)
    return _create_or_edit(entry, 'edit.html')

@app.template_filter('clean_querystring')
def clean_querystring(request_args, *keys_to_remove, **new_values):
    # We'll use this template filter in the pagination include. This filter
    # will take the current URL and allow us to preserve the arguments in the
    # querystring while replacing any that we need to overwrite. For instance
    # if your URL is /?q=search+query&page=2 and we want to preserve the search
    # term but make a link to page 3, this filter will allow us to do that.
    querystring = dict((key, value) for key, value in request_args.items())
    for key in keys_to_remove:
        querystring.pop(key, None)
    querystring.update(new_values)
    return urllib.urlencode(querystring)

@app.errorhandler(404)
def not_found(exc):
    return Response('<h3>Not found</h3>'), 404

def main():
    database.create_tables([Album,Photo,Entry, FTSEntry], safe=True)
    app.run(debug=True)

if __name__ == '__main__':
    main()
