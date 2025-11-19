from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# Flask Configuration
app.config['SECRET_KEY'] = 'replace_this_with_a_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'  # SQLite DB file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB and Login Manager
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# =========================================================
# Database Models
# =========================================================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    author = db.Column(db.String(200))
    isbn = db.Column(db.String(100), unique=True, nullable=True)
    quantity = db.Column(db.Integer, default=1)
    available = db.Column(db.Boolean, default=True)


class Borrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrowed_at = db.Column(db.DateTime, default=datetime.utcnow)
    returned_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref='borrows')
    book = db.relationship('Book', backref='borrows')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================================================
# Routes
# =========================================================

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ---------------- Registration ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register'))

        user = User(fullname=fullname, username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ---------------- Login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


# ---------------- Logout ----------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


# ---------------- Dashboard ----------------
@app.route('/dashboard')
@login_required
def dashboard():
    total_books = Book.query.count()
    total_users = User.query.count()
    borrowed = Borrow.query.filter_by(returned_at=None).count()
    return render_template('dashboard.html',
                           total_books=total_books,
                           total_users=total_users,
                           borrowed=borrowed)


# =========================================================
# Book Management
# =========================================================
@app.route('/books')
@login_required
def books():
    q = request.args.get('q', '')
    if q:
        books = Book.query.filter(Book.title.contains(q) | Book.author.contains(q)).all()
    else:
        books = Book.query.all()
    return render_template('books.html', books=books, q=q)


@app.route('/book/add', methods=['GET', 'POST'])
@login_required
def add_book():
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        quantity = int(request.form.get('quantity') or 1)

        if isbn and Book.query.filter_by(isbn=isbn).first():
            flash('A book with that ISBN already exists.', 'danger')
            return redirect(url_for('add_book'))

        book = Book(title=title, author=author, isbn=isbn,
                    quantity=quantity, available=(quantity > 0))
        db.session.add(book)
        db.session.commit()
        flash('Book added successfully.', 'success')
        return redirect(url_for('books'))
    return render_template('add_book.html')


@app.route('/book/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        book.title = request.form.get('title')
        book.author = request.form.get('author')
        book.isbn = request.form.get('isbn')
        book.quantity = int(request.form.get('quantity') or 1)
        book.available = book.quantity > 0
        db.session.commit()
        flash('Book updated successfully.', 'success')
        return redirect(url_for('books'))
    return render_template('edit_book.html', book=book)


@app.route('/book/delete/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    flash('Book deleted.', 'info')
    return redirect(url_for('books'))


# =========================================================
# Borrow / Return System
# =========================================================
@app.route('/borrow/<int:book_id>', methods=['POST'])
@login_required
def borrow(book_id):
    book = Book.query.get_or_404(book_id)
    if book.quantity <= 0:
        flash('Book not available.', 'danger')
        return redirect(url_for('books'))

    book.quantity -= 1
    if book.quantity == 0:
        book.available = False

    borrow_record = Borrow(user_id=current_user.id, book_id=book.id)
    db.session.add(borrow_record)
    db.session.commit()
    flash(f'You borrowed "{book.title}".', 'success')
    return redirect(url_for('books'))


@app.route('/return/<int:borrow_id>', methods=['POST'])
@login_required
def return_book(borrow_id):
    borrow = Borrow.query.get_or_404(borrow_id)
    if borrow.returned_at:
        flash('This book is already returned.', 'info')
        return redirect(url_for('dashboard'))

    borrow.returned_at = datetime.utcnow()
    book = Book.query.get(borrow.book_id)
    book.quantity += 1
    book.available = True
    db.session.commit()
    flash(f'Book "{book.title}" returned successfully.', 'success')
    return redirect(url_for('dashboard'))


# =========================================================
# Database Initialization (only once)
# =========================================================
@app.cli.command('init-db')
def init_db_command():
    """Initialize the database tables."""
    db.create_all()
    print('Database initialized successfully.')


# =========================================================
# Run Application
# =========================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
