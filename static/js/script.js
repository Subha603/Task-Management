document.addEventListener('DOMContentLoaded', function () {
    const todoForm = document.getElementById('todo-form');
    const todoList = document.getElementById('todo-list');
    const loginButton = document.getElementById('login-button');
    const todoApp = document.getElementById('todo-app');
    const errorMessage = document.getElementById('error-message');
    const loading = document.getElementById('loading');

    let isAuthenticated = false;

    // Check login status and load todos on page load
    async function initializeApp() {
        try {
            console.log('Checking authentication status...');
            const response = await fetch('/auth/status', {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache, no-store, must-revalidate'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Auth status check failed: ${response.status}`);
            }

            const data = await response.json();
            console.log('Auth status:', data);
            isAuthenticated = data.authenticated;

            if (loginButton && todoApp) {
                if (isAuthenticated) {
                    console.log('User is authenticated, showing todo app');
                    loginButton.style.display = 'none';
                    todoApp.style.display = 'block';
                    await loadTodos();
                } else {
                    console.log('User is not authenticated, showing login button');
                    loginButton.style.display = 'block';
                    todoApp.style.display = 'none';
                    window.location.href = '/login';
                }
            }
        } catch (error) {
            console.error('Initialization error:', error);
            showError('Failed to initialize app: ' + error.message);
        }
    }

    // Load all todos from the server
    async function loadTodos() {
        if (!todoList || !isAuthenticated) {
            console.log('Cannot load todos: todoList exists?', !!todoList, 'isAuthenticated?', isAuthenticated);
            return;
        }

        try {
            console.log('Loading todos...');
            loading.style.display = 'block';
            
            const response = await fetch('/todos', {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache, no-store, must-revalidate'
                },
                credentials: 'include'
            });

            console.log('Todos response status:', response.status);
            
            if (response.status === 401) {
                console.log('Session expired, redirecting to login');
                isAuthenticated = false;
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const todos = await response.json();
            console.log('Loaded todos:', todos);

            if (!Array.isArray(todos)) {
                console.error('Received invalid todos data:', todos);
                throw new Error('Invalid todos data received');
            }

            todoList.innerHTML = ''; // Clear existing todos

            // Sort todos by due date
            todos.sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
            
            todos.forEach(todo => {
                try {
                    addTodoToList(todo);
                } catch (e) {
                    console.error('Error adding todo to list:', e, todo);
                }
            });

            console.log('Todos loaded successfully');
        } catch (error) {
            console.error('Load todos error:', error);
            showError('Failed to load todos: ' + error.message);
            
            // If we get a 401 response, redirect to login
            if (error.message.includes('401')) {
                window.location.href = '/login';
            }
        } finally {
            loading.style.display = 'none';
        }
    }

    // Todo form submission handler
    if (todoForm) {
        todoForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!isAuthenticated) {
                showError('Please login first');
                return;
            }

            const titleInput = document.getElementById('title');
            const descriptionInput = document.getElementById('description');
            const dueDateInput = document.getElementById('due-date');

            if (!titleInput.value.trim() || !dueDateInput.value) {
                showError('Please fill in all required fields');
                return;
            }

            try {
                loading.style.display = 'block';
                const response = await fetch('/todos', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        title: titleInput.value.trim(),
                        description: descriptionInput.value.trim(),
                        due_date: dueDateInput.value
                    })
                });

                if (response.status === 401) {
                    isAuthenticated = false;
                    window.location.href = '/login';
                    return;
                }

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const todo = await response.json();
                console.log('Created new todo:', todo);
                
                // Clear the form
                todoForm.reset();
                
                // Reload all todos to ensure correct order
                await loadTodos();
            } catch (error) {
                console.error('Create todo error:', error);
                showError('Failed to create todo: ' + error.message);
            } finally {
                loading.style.display = 'none';
            }
        });
    }

    // Add a single todo to the list
    function addTodoToList(todo) {
        if (!todoList) return;

        console.log('Adding todo to list:', todo);

        const li = document.createElement('li');
        li.className = `todo-item ${todo.completed ? 'completed' : ''}`;
        li.dataset.id = todo.id;

        const dueDate = new Date(todo.due_date);
        const formattedDate = dueDate.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        li.innerHTML = `
            <div class="todo-content">
                <div class="todo-title">${escapeHtml(todo.title)}</div>
                <div class="todo-description">${escapeHtml(todo.description || '')}</div>
                <div class="todo-date" data-raw-date="${todo.due_date}">Due: ${formattedDate}</div>
            </div>
            <div class="todo-actions">
                <button class="btn btn-success toggle-btn" onclick="toggleTodo('${todo.id}', ${!todo.completed})">
                    ${todo.completed ? 'Undo' : 'Complete'}
                </button>
                <button class="btn btn-danger delete-btn" onclick="deleteTodo('${todo.id}')">Delete</button>
            </div>
        `;

        if (dueDate < new Date()) {
            li.classList.add('overdue');
        }

        todoList.appendChild(li);
    }

    // Toggle todo completion status
    window.toggleTodo = async function(id, completed) {
        if (!isAuthenticated) {
            showError('Please login first');
            return;
        }

        try {
            loading.style.display = 'block';
            const response = await fetch(`/todos/${id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({ completed })
            });

            if (response.status === 401) {
                isAuthenticated = false;
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Reload all todos to ensure correct order and state
            await loadTodos();
        } catch (error) {
            console.error('Update todo error:', error);
            showError('Failed to update todo: ' + error.message);
        } finally {
            loading.style.display = 'none';
        }
    };

    // Delete a todo
    window.deleteTodo = async function(id) {
        if (!isAuthenticated) {
            showError('Please login first');
            return;
        }
        
        if (!confirm('Are you sure you want to delete this todo?')) {
            return;
        }

        try {
            loading.style.display = 'block';
            const response = await fetch(`/todos/${id}`, {
                method: 'DELETE',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (response.status === 401) {
                isAuthenticated = false;
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Reload all todos to ensure correct state
            await loadTodos();
        } catch (error) {
            console.error('Delete todo error:', error);
            showError('Failed to delete todo: ' + error.message);
        } finally {
            loading.style.display = 'none';
        }
    };

    // Show error message
    function showError(message) {
        if (!errorMessage) return;

        console.error('Error:', message);
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
        setTimeout(() => {
            errorMessage.style.display = 'none';
        }, 3000);
    }

    // Helper function to escape HTML and prevent XSS
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Initialize the app
    initializeApp();

    // Add periodic refresh to keep todos up to date
    setInterval(loadTodos, 60000); // Refresh todos every minute
});